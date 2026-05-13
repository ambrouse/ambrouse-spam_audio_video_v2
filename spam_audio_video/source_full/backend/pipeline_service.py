from __future__ import annotations

import json
import time
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from auto_convert_text.storage.project_store import ProjectStore
from auto_convert_text.storage.shared_project_registry import SharedProjectRegistry


@dataclass
class PipelineResult:
    success: bool
    message: str
    manifest: dict | None = None
    stdout: str = ""
    stderr: str = ""


class AudioPipelineService:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root.resolve()
        self.auto_ttv_root = self.repo_root / "auto_text_to_voice"
        self.output_dir = self.auto_ttv_root / "output"
        self.manifest_path = self.output_dir / "manifest.json"
        self.combined_output = self.repo_root / "source_full" / "audio" / "combined.wav"
        self.voice_root = self.auto_ttv_root / "voice"
        self.text_root = self.auto_ttv_root / "text"
        self.source_audio_root = self.repo_root / "source_full" / "audio"
        self.source_video_root = self.repo_root / "source_full" / "video"
        self.worker_script = self.auto_ttv_root / "vieneu_worker.py"
        self._worker_proc: subprocess.Popen[str] | None = None
        self._worker_io_lock = threading.Lock()
        self.model_key = "voxcpm_vn"
        self.registry = SharedProjectRegistry(self.repo_root)
        self.project_store = ProjectStore(self.repo_root)
        self.project_store.migrate_legacy_projects()

    def _resolve_session_audio_paths(self, project_id: str, session_id: str) -> tuple[Path, Path, Path]:
        session_dir = self._resolve_existing_session_dir(project_id, session_id)
        audio_dir = session_dir / "audio"
        audio_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = audio_dir / "manifest.json"
        combined_output = audio_dir / "combined.wav"
        return audio_dir, manifest_path, combined_output

    def _resolve_session_audio_dir(self, project_id: str, session_id: str) -> Path:
        session_dir = self._resolve_existing_session_dir(project_id, session_id)
        audio_dir = session_dir / "audio"
        audio_dir.mkdir(parents=True, exist_ok=True)
        return audio_dir

    def _resolve_session_video_dir(self, project_id: str, session_id: str) -> Path:
        session_dir = self._resolve_existing_session_dir(project_id, session_id)
        video_dir = session_dir / "video"
        video_dir.mkdir(parents=True, exist_ok=True)
        return video_dir

    def _resolve_existing_session_dir(self, project_id: str, session_id: str) -> Path:
        session_dir = self.project_store.session_dir(project_id, session_id)
        if not session_dir.exists() or not session_dir.is_dir():
            sessions_root = self.project_store.project_dir(project_id) / "sessions"
            available: list[str] = []
            if sessions_root.exists():
                available = sorted(p.name for p in sessions_root.iterdir() if p.is_dir())
            suffix = f" Available sessions: {', '.join(available)}" if available else ""
            raise FileNotFoundError(
                f"Session not found for project '{project_id}': '{session_id}'.{suffix}"
            )
        return session_dir

    def resolve_audio_root(self, project_id: str | None = None, session_id: str | None = None) -> Path:
        if project_id and session_id:
            return self._resolve_session_audio_dir(project_id, session_id)
        return self.source_audio_root

    def resolve_video_root(self, project_id: str | None = None, session_id: str | None = None) -> Path:
        if project_id and session_id:
            return self._resolve_session_video_dir(project_id, session_id)
        return self.source_video_root

    @staticmethod
    def _sanitize_text_filename(filename: str) -> str:
        name = filename.strip().replace("\\", "/").split("/")[-1]
        if not name.lower().endswith(".txt"):
            name = f"{name}.txt"
        if name in {".txt", ""}:
            raise ValueError("Invalid text filename.")
        return name

    def _resolve_text_root(self, project_id: str | None = None, session_id: str | None = None) -> Path:
        if project_id and session_id:
            session_dir = self._resolve_existing_session_dir(project_id, session_id) / "tts_inputs"
            session_dir.mkdir(parents=True, exist_ok=True)
            return session_dir
        self.text_root.mkdir(parents=True, exist_ok=True)
        return self.text_root

    def _pick_python(self) -> Path | str:
        candidates = [
            self.auto_ttv_root / "VieNeu-TTS" / ".venv-win" / "Scripts" / "python.exe",
            self.auto_ttv_root / "VieNeu-TTS" / ".venv" / "Scripts" / "python.exe",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return "python"

    def list_voice_profiles(self) -> list[str]:
        if not self.voice_root.exists():
            return []
        names: list[str] = []
        for subdir in sorted(p for p in self.voice_root.iterdir() if p.is_dir()):
            has_audio = any(
                p.suffix.lower() in {".wav", ".mp3", ".flac", ".m4a", ".ogg"}
                for p in subdir.iterdir()
                if p.is_file()
            )
            has_text = any(p.suffix.lower() == ".txt" for p in subdir.iterdir() if p.is_file())
            if has_audio and has_text:
                names.append(subdir.name)
        return names

    def run(
        self,
        project_id: str | None = None,
        session_id: str | None = None,
        voice_profile: str | None = None,
        model_key: str | None = None,
        temperature: float = 0.80,
        top_k: int = 80,
        max_chars: int = 420,
        tts_io_workers: int = 2,
        inference_timesteps: int = 8,
        postprocess: bool = False,
        noise_reduction: float = 0.12,
        highpass_hz: float = 70.0,
        lowpass_hz: float = 10500.0,
        target_peak_db: float = -1.5,
        comp_threshold_db: float = -22.0,
        comp_ratio: float = 1.4,
        make_up_gain_db: float = 0.0,
        presence_boost_db: float = 0.4,
        de_ess: float = 0.30,
        gate_strength: float = 0.20,
        preprocess_reference: bool = False,
        anti_leak_trim: bool = True,
        anti_leak_max_ms: int = 900,
        progress_callback: Callable[[dict], None] | None = None,
    ) -> PipelineResult:
        if not self.worker_script.exists():
            return PipelineResult(False, f"Missing worker script: {self.worker_script}")
        if not project_id or not session_id:
            return PipelineResult(
                success=False,
                message="TTS phải chạy theo project/session. Vui lòng chọn project và session.",
            )
        output_dir, manifest_path, combined_output = self._resolve_session_audio_paths(project_id, session_id)
        clear_result = self.clear_session_audio_files(project_id, session_id)
        locked = clear_result.get("locked_files") or []
        if locked:
            return PipelineResult(
                success=False,
                message="Audio pipeline failed.",
                stderr=(
                    "Session audio contains locked files. "
                    "Hãy pause/đóng audio preview rồi Clear Session Audio trước khi chạy lại. "
                    f"Locked: {', '.join(locked)}"
                ),
            )
        text_dir_for_run = self._resolve_session_tts_inputs(project_id, session_id)
        text_files = sorted(text_dir_for_run.glob("*.txt"))
        total_text_files = max(1, len(text_files))
        if progress_callback:
            progress_callback({
                "stage": "tts_prepare",
                "current_units": 0,
                "total_units": total_text_files + 2,
                "message": f"Chuẩn bị TTS với {len(text_files)} file",
                "files_done": 0,
            })
        monitor_stop = threading.Event()
        monitor_thread: threading.Thread | None = None

        def monitor_outputs() -> None:
            while not monitor_stop.is_set():
                wav_files = sorted(output_dir.glob("*.wav"))
                wav_count = len(wav_files)
                latest_name = wav_files[-1].name if wav_files else ""
                if progress_callback:
                    progress_callback({
                        "stage": "tts_synth",
                        "current_units": min(total_text_files + 1, 1 + wav_count),
                        "total_units": total_text_files + 2,
                        "message": f"Đã tạo {wav_count}/{len(text_files)} file audio",
                        "files_done": wav_count,
                        "preview_text": latest_name,
                    })
                monitor_stop.wait(0.5)

        monitor_thread = threading.Thread(target=monitor_outputs, daemon=True)
        monitor_thread.start()
        try:
            payload = {
                "cmd": "synth",
                "project_root": str((self.auto_ttv_root / "VieNeu-TTS").resolve()),
                "voice_dir": str(self.voice_root.resolve()),
                "text_dir": str(text_dir_for_run.resolve()),
                "output_dir": str(output_dir.resolve()),
                "combined_output": str(combined_output.resolve()),
                "manifest_path": str(manifest_path.resolve()),
                "voice_profile": voice_profile or "",
                "model_key": model_key or self.model_key,
                "temperature": max(0.01, min(1.2, temperature)),
                "top_k": max(1, min(100, top_k)),
                "max_chars": max(80, min(420, max_chars)),
                "io_workers": max(1, min(6, int(tts_io_workers))),
                "inference_timesteps": max(4, min(20, int(inference_timesteps))),
                "device": "auto",
                "postprocess": bool(postprocess),
                "noise_reduction": max(0.0, min(1.0, noise_reduction)),
                "highpass_hz": max(20.0, min(250.0, highpass_hz)),
                "lowpass_hz": max(6000.0, min(16000.0, lowpass_hz)),
                "target_peak_db": max(-6.0, min(-0.1, target_peak_db)),
                "comp_threshold_db": max(-36.0, min(-8.0, comp_threshold_db)),
                "comp_ratio": max(1.0, min(8.0, comp_ratio)),
                "make_up_gain_db": max(0.0, min(12.0, make_up_gain_db)),
                "presence_boost_db": max(-3.0, min(6.0, presence_boost_db)),
                "de_ess": max(0.0, min(1.0, de_ess)),
                "gate_strength": max(0.0, min(1.0, gate_strength)),
                "preprocess_reference": False,
                "anti_leak_trim": bool(anti_leak_trim),
                "anti_leak_max_ms": max(80, min(1200, int(anti_leak_max_ms))),
                "head_pre_roll_ms": 10,
                "tail_keep_ms": 100,
                "project_id": project_id or "",
                "session_id": session_id or "",
            }
            reply = self._send_worker(payload)
        except Exception as exc:  # pylint: disable=broad-except
            monitor_stop.set()
            if monitor_thread:
                monitor_thread.join(timeout=2.0)
            return PipelineResult(
                success=False,
                message="Audio pipeline failed.",
                stderr=str(exc),
            )
        finally:
            monitor_stop.set()
            if monitor_thread:
                monitor_thread.join(timeout=2.0)

        if not reply.get("ok"):
            return PipelineResult(
                success=False,
                message="Audio pipeline failed.",
                stdout="\n".join(reply.get("logs", [])),
                stderr=str(reply.get("error", "Unknown worker error")),
            )

        manifest = None
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if project_id:
                manifest["project_id"] = project_id
                manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        if progress_callback:
            generated_count = len(manifest.get("outputs", [])) if manifest else 0
            progress_callback({
                "stage": "tts_done",
                "current_units": total_text_files + 2,
                "total_units": total_text_files + 2,
                "message": f"Hoàn tất TTS, tạo {generated_count} file",
                "files_done": generated_count,
            })

        if project_id:
            generated = 0
            if manifest:
                generated = len(manifest.get("items", []) or manifest.get("files", []) or [])
            self.registry.update_tts(
                project_id,
                {
                    "voice_profile": voice_profile or "",
                    "model_key": model_key or self.model_key,
                    "manifest_path": str(manifest_path.relative_to(self.repo_root)),
                    "combined_output": str(combined_output.relative_to(self.repo_root)),
                    "generated_files": generated,
                },
            )
            self.registry.upsert_project(project_id, {"status": "audio_ready"})
            if session_id:
                self.registry.upsert_session(
                    project_id,
                    session_id,
                    {
                            "status": "audio_ready",
                            "tts": {
                                "voice_profile": voice_profile or "",
                                "model_key": model_key or self.model_key,
                                "manifest_path": str(manifest_path.relative_to(self.repo_root)),
                                "combined_output": str(combined_output.relative_to(self.repo_root)),
                                "generated_files": generated,
                            },
                        },
                )

        return PipelineResult(
            success=True,
            message="Audio pipeline completed successfully.",
            manifest=manifest,
            stdout="\n".join(reply.get("logs", [])),
            stderr="",
        )

    def prewarm(self) -> dict:
        payload = {
            "cmd": "prewarm",
            "project_root": str((self.auto_ttv_root / "VieNeu-TTS").resolve()),
            "device": "auto",
            "model_key": self.model_key,
        }
        return self._send_worker(payload)

    def list_models(self) -> dict:
        payload = {"cmd": "list_models"}
        try:
            return self._send_worker(payload)
        except Exception as exc:  # pylint: disable=broad-except
            return {
                "ok": False,
                "selected_model": self.model_key,
                "models": [
                    {
                        "key": "voxcpm_vn",
                        "label": "VoxCPM 1.5 VN (Clone)",
                        "selected": "true" if self.model_key == "voxcpm_vn" else "false",
                    }
                ],
                "runtime_error": str(exc),
                "message": "TTS worker is not ready. Install/load the VieNeu/VoxCPM runtime before audio synthesis.",
            }

    def set_model(self, model_key: str) -> dict:
        self.model_key = model_key
        payload = {
            "cmd": "set_model",
            "model_key": model_key,
            "project_root": str((self.auto_ttv_root / "VieNeu-TTS").resolve()),
            "device": "auto",
        }
        return self._send_worker(payload)

    def _start_worker(self) -> None:
        python_exec = self._pick_python()
        self._worker_proc = subprocess.Popen(
            [str(python_exec), str(self.worker_script.resolve())],
            cwd=str(self.repo_root),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )

    def _ensure_worker(self) -> None:
        if self._worker_proc is None or self._worker_proc.poll() is not None:
            self._start_worker()

    def _send_worker(self, payload: dict) -> dict:
        with self._worker_io_lock:
            self._ensure_worker()
            assert self._worker_proc is not None
            assert self._worker_proc.stdin is not None
            assert self._worker_proc.stdout is not None

            self._worker_proc.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
            self._worker_proc.stdin.flush()
            while True:
                line = self._worker_proc.stdout.readline()
                if not line:
                    raise RuntimeError("Worker exited unexpectedly.")
                line = line.strip()
                if not line:
                    continue
                try:
                    return json.loads(line)
                except json.JSONDecodeError:
                    continue

    def reset_runtime(self) -> dict:
        with self._worker_io_lock:
            if self._worker_proc is None or self._worker_proc.poll() is not None:
                self._worker_proc = None
                return {"ok": True, "message": "Worker runtime already stopped."}
            try:
                assert self._worker_proc.stdin is not None
                self._worker_proc.stdin.write(json.dumps({"cmd": "shutdown"}) + "\n")
                self._worker_proc.stdin.flush()
            except Exception:
                pass
            try:
                self._worker_proc.terminate()
                self._worker_proc.wait(timeout=5)
            except Exception:
                try:
                    self._worker_proc.kill()
                except Exception:
                    pass
            finally:
                self._worker_proc = None
        return {"ok": True, "message": "Worker runtime reset. Next run will load fresh model/reference."}

    def _resolve_session_tts_inputs(self, project_id: str, session_id: str) -> Path:
        source_dir = self.project_store.session_dir(project_id, session_id) / "tts_inputs"
        source_dir.mkdir(parents=True, exist_ok=True)
        files = sorted(source_dir.glob("*.txt"))
        if not files:
            self._auto_export_session_tts_inputs_from_audio_clean(project_id, session_id)
            files = sorted(source_dir.glob("*.txt"))
        if not files:
            available = self._sessions_with_tts_inputs(project_id)
            suffix = f" Available sessions with TTS inputs: {', '.join(available)}" if available else ""
            raise FileNotFoundError(f"No session TTS input files found: {source_dir}.{suffix}")
        return source_dir

    def _sessions_with_tts_inputs(self, project_id: str) -> list[str]:
        sessions_root = self.project_store.project_dir(project_id) / "sessions"
        if not sessions_root.exists():
            return []
        available: list[str] = []
        for session_dir in sorted(p for p in sessions_root.iterdir() if p.is_dir()):
            tts_dir = session_dir / "tts_inputs"
            if tts_dir.exists() and any(tts_dir.glob("*.txt")):
                available.append(session_dir.name)
        return available

    def _auto_export_session_tts_inputs_from_audio_clean(self, project_id: str, session_id: str) -> int:
        import re

        session_dir = self.project_store.session_dir(project_id, session_id)
        clean_dir = session_dir / "chapters_text" / "audio_clean"
        if not clean_dir.exists():
            return 0
        chapter_files = sorted(clean_dir.glob("chapter_*.txt"))
        if not chapter_files:
            return 0
        target_dir = session_dir / "tts_inputs"
        target_dir.mkdir(parents=True, exist_ok=True)
        exported = 0
        for old in target_dir.glob("*.txt"):
            old.unlink(missing_ok=True)

        def split_sentences(text: str) -> list[str]:
            compact = " ".join((text or "").split())
            if not compact:
                return []
            return [p.strip(" ,") for p in re.split(r"(?<=[.!?])\s+", compact) if p.strip(" ,")]

        def sanitize_tts_input_text(text: str) -> str:
            compact = " ".join((text or "").split()).strip()
            compact = re.sub(r"[.,]+\s*$", "", compact)
            return compact.strip()

        for chapter_path in chapter_files:
            text = chapter_path.read_text(encoding="utf-8", errors="replace").strip()
            if not text:
                continue
            for sentence in split_sentences(text):
                exported += 1
                out_name = f"text_{exported:04d}.txt"
                out_path = target_dir / out_name
                out_path.write_text(sanitize_tts_input_text(sentence), encoding="utf-8")
        return exported

    @staticmethod
    def _remove_files_by_suffix(folder: Path, suffixes: set[str]) -> int:
        if not folder.exists():
            return 0
        removed = 0
        for f in folder.iterdir():
            if f.is_file() and f.suffix.lower() in suffixes:
                f.unlink(missing_ok=True)
                removed += 1
        return removed

    @staticmethod
    def _remove_all_files(folder: Path) -> int:
        if not folder.exists():
            return 0
        removed = 0
        for f in folder.iterdir():
            if f.is_file():
                f.unlink(missing_ok=True)
                removed += 1
        return removed

    def clear_text_files(self) -> dict:
        count = self._remove_files_by_suffix(self.text_root, {".txt"})
        return {"message": "Cleared text files.", "removed": count}

    def list_text_files(self, project_id: str | None = None, session_id: str | None = None) -> dict:
        root = self._resolve_text_root(project_id, session_id)
        files = []
        for p in sorted(root.iterdir()):
            if p.is_file() and p.suffix.lower() == ".txt":
                files.append({"name": p.name, "size": p.stat().st_size})
        return {"files": files, "root": str(root.relative_to(self.repo_root))}

    def get_text_file_content(self, filename: str, project_id: str | None = None, session_id: str | None = None) -> dict:
        safe_name = self._sanitize_text_filename(filename)
        root = self._resolve_text_root(project_id, session_id)
        target = (root / safe_name).resolve()
        if target.parent != root.resolve() or not target.exists() or not target.is_file():
            raise FileNotFoundError(f"Text file not found: {safe_name}")
        content = target.read_text(encoding="utf-8", errors="replace")
        return {"name": safe_name, "content": content, "root": str(root.relative_to(self.repo_root))}

    def save_text_file_content(
        self,
        filename: str,
        content: str,
        project_id: str | None = None,
        session_id: str | None = None,
    ) -> dict:
        safe_name = self._sanitize_text_filename(filename)
        root = self._resolve_text_root(project_id, session_id)
        target = (root / safe_name).resolve()
        if target.parent != root.resolve():
            raise ValueError("Invalid text filename.")
        target.write_text(content, encoding="utf-8")
        return {"message": "Saved text file.", "name": safe_name, "size": target.stat().st_size, "root": str(root.relative_to(self.repo_root))}

    def delete_text_file(self, filename: str, project_id: str | None = None, session_id: str | None = None) -> dict:
        safe_name = self._sanitize_text_filename(filename)
        root = self._resolve_text_root(project_id, session_id)
        target = (root / safe_name).resolve()
        if target.parent != root.resolve() or not target.exists() or not target.is_file():
            raise FileNotFoundError(f"Text file not found: {safe_name}")
        target.unlink(missing_ok=True)
        return {"message": "Deleted text file.", "name": safe_name, "root": str(root.relative_to(self.repo_root))}

    def clear_auto_output_audio(self) -> dict:
        count = self._remove_files_by_suffix(self.output_dir, {".wav"})
        manifest_removed = 0
        if self.manifest_path.exists():
            self.manifest_path.unlink(missing_ok=True)
            manifest_removed = 1
        return {
            "message": "Cleared auto_text_to_voice output audio files.",
            "removed_wav": count,
            "removed_manifest": manifest_removed,
        }

    def clear_source_full_audio_video(self) -> dict:
        removed_audio = self._remove_all_files(self.source_audio_root)
        removed_video = self._remove_all_files(self.source_video_root)
        return {
            "message": "Cleared source_full audio and video files.",
            "removed_audio": removed_audio,
            "removed_video": removed_video,
        }

    def clear_session_audio_files(self, project_id: str, session_id: str) -> dict:
        audio_dir, manifest_path, _combined_output = self._resolve_session_audio_paths(project_id, session_id)
        removed = 0
        locked_files: list[str] = []

        def try_remove_file(path: Path) -> bool:
            retries = 3
            for attempt in range(1, retries + 1):
                try:
                    if path.exists():
                        path.unlink(missing_ok=True)
                    return True
                except PermissionError:
                    if attempt >= retries:
                        return False
                    time.sleep(0.35)
                except OSError as exc:
                    if attempt >= retries:
                        if getattr(exc, "winerror", None) == 32:
                            return False
                        raise
                    time.sleep(0.35)
            return False

        for wav in sorted(audio_dir.glob("*.wav")):
            if try_remove_file(wav):
                removed += 1
            else:
                locked_files.append(wav.name)

        manifest_removed = False
        if manifest_path.exists():
            if try_remove_file(manifest_path):
                manifest_removed = True
            else:
                locked_files.append(manifest_path.name)

        return {
            "message": "Cleared session audio files." if not locked_files else "Session audio clear partially completed.",
            "project_id": project_id,
            "session_id": session_id,
            "audio_dir": str(audio_dir.relative_to(self.repo_root)),
            "removed_wav": removed,
            "removed_manifest": 1 if manifest_removed else 0,
            "locked_files": locked_files,
        }

    def clear_session_video_files(self, project_id: str, session_id: str) -> dict:
        video_dir = self._resolve_session_video_dir(project_id, session_id)
        removed = 0
        locked_files: list[str] = []
        video_exts = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}

        def try_remove_file(path: Path) -> bool:
            retries = 3
            for attempt in range(1, retries + 1):
                try:
                    if path.exists():
                        path.unlink(missing_ok=True)
                    return True
                except PermissionError:
                    if attempt >= retries:
                        return False
                    time.sleep(0.35)
                except OSError as exc:
                    if attempt >= retries:
                        if getattr(exc, "winerror", None) == 32:
                            return False
                        raise
                    time.sleep(0.35)
            return False

        for video_file in sorted(p for p in video_dir.glob("*") if p.is_file() and p.suffix.lower() in video_exts):
            if try_remove_file(video_file):
                removed += 1
            else:
                locked_files.append(video_file.name)

        return {
            "message": "Cleared session video files." if not locked_files else "Session video clear partially completed.",
            "project_id": project_id,
            "session_id": session_id,
            "video_dir": str(video_dir.relative_to(self.repo_root)),
            "removed_video": removed,
            "locked_files": locked_files,
        }

    def clear_session_video_images_files(self, project_id: str, session_id: str) -> dict:
        video_dir = self._resolve_session_video_dir(project_id, session_id)
        images_dir = video_dir / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        removed = 0
        locked_files: list[str] = []
        image_exts = {".png", ".jpg", ".jpeg", ".webp"}

        def try_remove_file(path: Path) -> bool:
            retries = 3
            for attempt in range(1, retries + 1):
                try:
                    if path.exists():
                        path.unlink(missing_ok=True)
                    return True
                except PermissionError:
                    if attempt >= retries:
                        return False
                    time.sleep(0.35)
                except OSError as exc:
                    if attempt >= retries:
                        if getattr(exc, "winerror", None) == 32:
                            return False
                        raise
                    time.sleep(0.35)
            return False

        for image_file in sorted(p for p in images_dir.glob("*") if p.is_file() and p.suffix.lower() in image_exts):
            if try_remove_file(image_file):
                removed += 1
            else:
                locked_files.append(image_file.name)

        return {
            "message": "Cleared session image files." if not locked_files else "Session image clear partially completed.",
            "project_id": project_id,
            "session_id": session_id,
            "images_dir": str(images_dir.relative_to(self.repo_root)),
            "removed_images": removed,
            "locked_files": locked_files,
        }

    def clear_session_stage_files(self, project_id: str, session_id: str, stage: str) -> dict:
        session_dir = self._resolve_existing_session_dir(project_id, session_id)
        stage_key = (stage or "").strip().lower()
        stage_dirs = {
            "raw": session_dir / "chapters_text" / "raw",
            "rewrite": session_dir / "chapters_text" / "rewritten",
            "rewritten": session_dir / "chapters_text" / "rewritten",
            "audio_clean": session_dir / "chapters_text" / "audio_clean",
            "chunks": session_dir / "chapters_text" / "chunks",
            "tts_inputs": session_dir / "tts_inputs",
            "all_text": None,
        }
        if stage_key not in stage_dirs:
            allowed = ", ".join(sorted(stage_dirs.keys()))
            raise ValueError(f"Invalid stage '{stage}'. Allowed: {allowed}")

        if stage_key == "all_text":
            targets = [
                session_dir / "chapters_text" / "raw",
                session_dir / "chapters_text" / "rewritten",
                session_dir / "chapters_text" / "audio_clean",
                session_dir / "chapters_text" / "chunks",
                session_dir / "tts_inputs",
            ]
        else:
            targets = [stage_dirs[stage_key]]

        removed = 0
        removed_by_dir: dict[str, int] = {}
        for target in targets:
            count = self._remove_files_by_suffix(target, {".txt"})
            removed += count
            removed_by_dir[str(target.relative_to(self.repo_root))] = count

        return {
            "message": "Cleared session stage text files.",
            "project_id": project_id,
            "session_id": session_id,
            "stage": stage_key,
            "removed": removed,
            "removed_by_dir": removed_by_dir,
        }

    def list_source_media_files(self, project_id: str | None = None, session_id: str | None = None) -> dict:
        audio_files = []
        video_files = []
        audio_exts = {".wav", ".mp3", ".flac", ".m4a", ".ogg"}
        video_exts = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}
        if project_id and session_id:
            session_audio_dir = self._resolve_session_audio_dir(project_id, session_id)
            if session_audio_dir.exists():
                audio_files = sorted(
                    p.name
                    for p in session_audio_dir.iterdir()
                    if p.is_file() and p.suffix.lower() in audio_exts
                )
            session_video_dir = self._resolve_session_video_dir(project_id, session_id)
            if session_video_dir.exists():
                video_files = sorted(
                    p.name
                    for p in session_video_dir.iterdir()
                    if p.is_file() and p.suffix.lower() in video_exts
                )
        elif self.source_audio_root.exists():
            audio_files = sorted(
                p.name
                for p in self.source_audio_root.iterdir()
                if p.is_file() and p.suffix.lower() in audio_exts
            )
        if not video_files and self.source_video_root.exists():
            video_files = sorted(
                p.name
                for p in self.source_video_root.iterdir()
                if p.is_file() and p.suffix.lower() in video_exts
            )
        return {"audio_files": audio_files, "video_files": video_files}
