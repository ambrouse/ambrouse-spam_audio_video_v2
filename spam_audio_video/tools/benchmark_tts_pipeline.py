from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
import wave
from datetime import datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(REPO_ROOT / "source_full" / "backend") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "source_full" / "backend"))

from pipeline_service import AudioPipelineService


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^0-9A-Za-z_.-]+", "_", str(value or "").strip())
    return slug.strip("._") or "run"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _create_artifact_dir(root: Path, scenario: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    artifact_dir = root / f"{stamp}_{_safe_slug(scenario)}"
    for child in ("input", "output/chunks", "reports", "logs", "audio_samples"):
        (artifact_dir / child).mkdir(parents=True, exist_ok=True)
    return artifact_dir


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _wav_metadata(path: Path) -> dict:
    if not path.exists():
        return {"exists": False}
    try:
        with wave.open(str(path), "rb") as handle:
            frames = handle.getnframes()
            rate = handle.getframerate()
            channels = handle.getnchannels()
            width = handle.getsampwidth()
        return {
            "exists": True,
            "path": str(path),
            "size": path.stat().st_size,
            "sha256": _sha256_file(path),
            "sample_rate": rate,
            "channels": channels,
            "sample_width_bytes": width,
            "frames": frames,
            "duration_s": round(frames / rate, 3) if rate else 0,
        }
    except wave.Error as exc:
        return {
            "exists": True,
            "path": str(path),
            "size": path.stat().st_size,
            "sha256": _sha256_file(path),
            "error": str(exc),
        }


def _parse_worker_logs(stdout: str) -> dict:
    infer_values: list[int] = []
    io_values: list[int] = []
    cache_hits = 0
    saved = 0
    for line in stdout.splitlines():
        if "cache hit" in line:
            cache_hits += 1
        if "] saved " in line:
            saved += 1
        infer = re.search(r"infer_ms=(\d+)", line)
        if infer:
            infer_values.append(int(infer.group(1)))
        io_match = re.search(r"io_ms=(\d+)", line)
        if io_match:
            io_values.append(int(io_match.group(1)))
    return {
        "saved_lines": saved,
        "cache_hit_lines": cache_hits,
        "infer_ms": {
            "count": len(infer_values),
            "total": sum(infer_values),
            "avg": round(sum(infer_values) / len(infer_values), 3) if infer_values else 0,
            "max": max(infer_values) if infer_values else 0,
        },
        "io_ms": {
            "count": len(io_values),
            "total": sum(io_values),
            "avg": round(sum(io_values) / len(io_values), 3) if io_values else 0,
            "max": max(io_values) if io_values else 0,
        },
    }


def _copy_input_manifest(source_session: Path, artifact_dir: Path, project_id: str, session_id: str) -> list[Path]:
    tts_dir = source_session / "tts_inputs"
    text_files = sorted(tts_dir.glob("*.txt"))
    manifest = {
        "project_id": project_id,
        "session_id": session_id,
        "session_dir": str(source_session),
        "tts_input_count": len(text_files),
        "tts_inputs": [
            {
                "name": path.name,
                "size": path.stat().st_size,
                "sha256": _sha256_file(path),
            }
            for path in text_files
        ],
    }
    _write_json(artifact_dir / "input" / "source_manifest.json", manifest)
    for name in ("session.json", "chunks_manifest.json", "audio_clean_manifest.json"):
        src = source_session / name
        if src.exists():
            shutil.copy2(src, artifact_dir / "input" / name)
    return text_files


def _make_limited_session(source_session: Path, project_id: str, session_id: str, text_limit: int) -> tuple[str, str, Path]:
    limited_project = f"{project_id}-bench-audio"
    limited_session = f"{session_id}-limit-{text_limit}"
    target_session = REPO_ROOT / "projects_workspace" / "projects" / _safe_slug(limited_project).lower() / "sessions" / _safe_slug(limited_session).lower()
    if target_session.exists():
        shutil.rmtree(target_session)
    (target_session / "tts_inputs").mkdir(parents=True, exist_ok=True)
    for src in sorted((source_session / "tts_inputs").glob("*.txt"))[:text_limit]:
        shutil.copy2(src, target_session / "tts_inputs" / src.name)
    session_json = source_session / "session.json"
    if session_json.exists():
        shutil.copy2(session_json, target_session / "session.json")
    else:
        _write_json(target_session / "session.json", {"project_id": limited_project, "session_id": limited_session})
    return limited_project, limited_session, target_session


def _copy_outputs(audio_dir: Path, artifact_dir: Path) -> dict:
    copied: list[dict] = []
    for wav_path in sorted(audio_dir.glob("*.wav")):
        if wav_path.name == "combined.wav":
            shutil.copy2(wav_path, artifact_dir / "output" / "combined.wav")
        else:
            shutil.copy2(wav_path, artifact_dir / "output" / "chunks" / wav_path.name)
        copied.append(_wav_metadata(wav_path))
    manifest_path = audio_dir / "manifest.json"
    if manifest_path.exists():
        shutil.copy2(manifest_path, artifact_dir / "reports" / "manifest.json")
    return {
        "count": len(copied),
        "files": copied,
        "combined": _wav_metadata(audio_dir / "combined.wav"),
    }


def _write_summary(path: Path, report: dict) -> None:
    target = report.get("target", {})
    lines = [
        "# TTS Pipeline Benchmark Summary",
        "",
        f"- Success: `{report.get('success')}`",
        f"- Project/session: `{report.get('project_id')}/{report.get('session_id')}`",
        f"- Elapsed seconds: `{report.get('elapsed_s')}`",
        f"- Audio duration seconds: `{report.get('audio', {}).get('combined', {}).get('duration_s', 0)}`",
        f"- Cache enabled: `{report.get('config', {}).get('cache_enabled')}`",
        f"- Cache hits: `{report.get('manifest_cache', {}).get('hits', 0)}`",
        f"- Cache misses: `{report.get('manifest_cache', {}).get('misses', 0)}`",
        f"- Baseline seconds: `{target.get('baseline_elapsed_s', 0)}`",
        f"- Multiplier vs baseline: `{target.get('multiplier_vs_baseline', 0)}`",
        f"- Pass 4x target: `{target.get('pass_4x', False)}`",
        f"- Main first-run pass 4x: `{target.get('main_first_run_pass_4x', False)}`",
    ]
    _write_text(path, "\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark the real VoxCPM/VieNeu TTS pipeline.")
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--voice-profile", default="")
    parser.add_argument("--model-key", default="voxcpm_vn")
    parser.add_argument("--temperature", type=float, default=0.05)
    parser.add_argument("--top-k", type=int, default=80)
    parser.add_argument("--tts-io-workers", type=int, default=6)
    parser.add_argument("--inference-timesteps", type=int, default=8)
    parser.add_argument("--postprocess", action="store_true")
    parser.add_argument("--cache-enabled", action="store_true")
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--text-limit", type=int, default=0)
    parser.add_argument("--merge-inputs", type=int, default=0, help="Merge N source text chunks into one benchmark TTS input chunk.")
    parser.add_argument("--scenario", default="real_session_tts")
    parser.add_argument("--artifact-root", default=str(REPO_ROOT / "benchmarks" / "audio_8x4x"))
    parser.add_argument("--baseline-elapsed-s", type=float, default=0)
    args = parser.parse_args()

    service = AudioPipelineService(REPO_ROOT)
    source_session = service.project_store.session_dir(args.project_id, args.session_id)
    project_id = args.project_id
    session_id = args.session_id
    benchmark_session = source_session
    if args.text_limit > 0:
        project_id, session_id, benchmark_session = _make_limited_session(source_session, args.project_id, args.session_id, args.text_limit)
    if args.merge_inputs > 1:
        source_texts = sorted((benchmark_session / "tts_inputs").glob("*.txt"))
        merged_project = f"{args.project_id}-bench-audio-merged"
        merged_session = f"{args.session_id}-merge-{args.merge_inputs}-limit-{len(source_texts)}"
        merged_dir = REPO_ROOT / "projects_workspace" / "projects" / _safe_slug(merged_project).lower() / "sessions" / _safe_slug(merged_session).lower()
        if merged_dir.exists():
            shutil.rmtree(merged_dir)
        (merged_dir / "tts_inputs").mkdir(parents=True, exist_ok=True)
        group_index = 1
        for offset in range(0, len(source_texts), int(args.merge_inputs)):
            group = source_texts[offset : offset + int(args.merge_inputs)]
            merged_text = " ".join(path.read_text(encoding="utf-8", errors="replace").strip() for path in group if path.exists()).strip()
            if merged_text and not merged_text.endswith("."):
                merged_text += "."
            (merged_dir / "tts_inputs" / f"text_{group_index:04d}.txt").write_text(merged_text + "\n", encoding="utf-8")
            group_index += 1
        session_json = benchmark_session / "session.json"
        if session_json.exists():
            shutil.copy2(session_json, merged_dir / "session.json")
        else:
            _write_json(merged_dir / "session.json", {"project_id": merged_project, "session_id": merged_session})
        project_id, session_id, benchmark_session = merged_project, merged_session, merged_dir

    artifact_dir = _create_artifact_dir(Path(args.artifact_root), args.scenario)
    _copy_input_manifest(benchmark_session, artifact_dir, project_id, session_id)
    cache_enabled = bool(args.cache_enabled and not args.no_cache)
    config = {
        "voice_profile": args.voice_profile,
        "model_key": args.model_key,
        "temperature": max(0.01, min(1.2, float(args.temperature))),
        "top_k": max(1, min(100, int(args.top_k))),
        "tts_io_workers": max(1, int(args.tts_io_workers)),
        "inference_timesteps": max(4, int(args.inference_timesteps)),
        "postprocess": bool(args.postprocess),
        "cache_enabled": cache_enabled,
        "text_limit": int(args.text_limit),
        "merge_inputs": int(args.merge_inputs),
    }
    _write_json(artifact_dir / "input" / "benchmark_config.json", config)

    started = time.perf_counter()
    result = service.run(
        project_id=project_id,
        session_id=session_id,
        voice_profile=args.voice_profile or None,
        model_key=args.model_key,
        temperature=args.temperature,
        top_k=args.top_k,
        tts_io_workers=args.tts_io_workers,
        inference_timesteps=args.inference_timesteps,
        postprocess=args.postprocess,
        tts_cache_enabled=cache_enabled,
    )
    elapsed_s = time.perf_counter() - started
    audio_dir, manifest_path, combined_output = service._resolve_session_audio_paths(project_id, session_id)  # pylint: disable=protected-access
    audio_report = _copy_outputs(audio_dir, artifact_dir)
    manifest = {}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    parsed_logs = _parse_worker_logs(result.stdout)
    manifest_cache = manifest.get("cache", {})
    cache_hits = int(manifest_cache.get("hits") or 0) if isinstance(manifest_cache, dict) else 0
    first_run_candidate = cache_hits == 0
    baseline = float(args.baseline_elapsed_s)
    multiplier = round(baseline / elapsed_s, 4) if baseline > 0 and elapsed_s > 0 else 0
    pass_4x = bool(multiplier >= 4.0)
    report = {
        "success": bool(result.success),
        "message": result.message,
        "project_id": project_id,
        "session_id": session_id,
        "source_project_id": args.project_id,
        "source_session_id": args.session_id,
        "elapsed_s": round(elapsed_s, 3),
        "config": config,
        "audio": audio_report,
        "combined_output": str(combined_output),
        "manifest_cache": manifest_cache,
        "parsed_worker_logs": parsed_logs,
        "target": {
            "baseline_elapsed_s": baseline,
            "multiplier_vs_baseline": multiplier,
            "pass_4x": pass_4x,
            "first_run_candidate": first_run_candidate,
            "main_first_run_pass_4x": bool(first_run_candidate and pass_4x),
            "max_elapsed_for_4x_s": round(baseline / 4.0, 3) if baseline > 0 else 0,
            "note": "main_first_run_pass_4x ignores cache-hit acceleration; cache-hit runs are secondary evidence only.",
        },
        "artifact_dir": str(artifact_dir),
        "stderr": result.stderr,
    }
    _write_json(artifact_dir / "reports" / "benchmark.json", report)
    _write_json(artifact_dir / "reports" / "quality.json", {
        "success": bool(result.success and audio_report.get("combined", {}).get("exists")),
        "combined_wav": audio_report.get("combined", {}),
        "note": "Audio quality requires manual listening for non-cache acceleration; cache hits reuse exact WAV files.",
    })
    _write_summary(artifact_dir / "reports" / "summary.md", report)
    _write_text(artifact_dir / "logs" / "worker_stdout.log", result.stdout)
    _write_text(artifact_dir / "logs" / "worker_stderr.txt", result.stderr)
    try:
        nvidia = subprocess.run(
            ["nvidia-smi"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
            check=False,
        )
        _write_text(artifact_dir / "logs" / "nvidia_smi.txt", f"{nvidia.stdout}\n{nvidia.stderr}")
    except Exception as exc:  # pylint: disable=broad-except
        _write_text(artifact_dir / "logs" / "nvidia_smi.txt", str(exc))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
