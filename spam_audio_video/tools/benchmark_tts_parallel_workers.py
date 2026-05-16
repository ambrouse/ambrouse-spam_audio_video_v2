from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import wave
from datetime import datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKER_SCRIPT = REPO_ROOT / "auto_text_to_voice" / "vieneu_worker.py"
TTS_ROOT = REPO_ROOT / "auto_text_to_voice"


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^0-9A-Za-z_.-]+", "_", str(value or "").strip())
    return slug.strip("._").lower() or "run"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _create_artifact_dir(root: Path, scenario: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    artifact_dir = root / f"{stamp}_{_safe_slug(scenario)}"
    for child in ("input", "output/chunks", "reports", "logs", "audio_samples", "work"):
        (artifact_dir / child).mkdir(parents=True, exist_ok=True)
    return artifact_dir


def _pick_python() -> str:
    candidates = [
        TTS_ROOT / "VieNeu-TTS" / ".venv-win" / "Scripts" / "python.exe",
        TTS_ROOT / "VieNeu-TTS" / ".venv" / "Scripts" / "python.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return sys.executable


def _wav_metadata(path: Path) -> dict:
    if not path.exists():
        return {"exists": False}
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


def _parse_worker_logs(logs: list[str]) -> dict:
    infer_values: list[int] = []
    io_values: list[int] = []
    for line in logs:
        infer = re.search(r"infer_ms=(\d+)", line)
        if infer:
            infer_values.append(int(infer.group(1)))
        io_match = re.search(r"io_ms=(\d+)", line)
        if io_match:
            io_values.append(int(io_match.group(1)))
    return {
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


def _round_robin_split(paths: list[Path], workers: int) -> list[list[Path]]:
    groups = [[] for _ in range(workers)]
    for index, path in enumerate(paths):
        groups[index % workers].append(path)
    return groups


def _send_worker(proc: subprocess.Popen[str], payload: dict) -> dict:
    assert proc.stdin is not None
    assert proc.stdout is not None
    proc.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
    proc.stdin.flush()
    while True:
        line = proc.stdout.readline()
        if not line:
            raise RuntimeError("worker exited before reply")
        line = line.strip()
        if line:
            return json.loads(line)


def _read_worker_reply(proc: subprocess.Popen[str]) -> dict:
    assert proc.stdout is not None
    while True:
        line = proc.stdout.readline()
        if not line:
            raise RuntimeError("worker exited before reply")
        line = line.strip()
        if line:
            return json.loads(line)


def _launch_worker(python_exec: str, stderr_path: Path) -> subprocess.Popen[str]:
    stderr_path.parent.mkdir(parents=True, exist_ok=True)
    stderr_handle = stderr_path.open("w", encoding="utf-8", errors="replace")
    return subprocess.Popen(
        [python_exec, str(WORKER_SCRIPT)],
        cwd=str(REPO_ROOT),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=stderr_handle,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )


def _suggest_pause_ms_from_text(text: str) -> int:
    compact = (text or "").strip()
    if compact.endswith(","):
        return 140
    if compact.endswith(";") or compact.endswith(":"):
        return 260
    if compact.endswith(".") or compact.endswith("!") or compact.endswith("?"):
        return 320
    return 220


def _merge_wavs(paths: list[Path], source_texts: list[Path], output_path: Path) -> None:
    import numpy as np
    import soundfile as sf

    chunks = []
    sample_rate = None
    channels = None
    for index, wav_path in enumerate(paths):
        audio, sr = sf.read(str(wav_path), dtype="float32", always_2d=True)
        if sample_rate is None:
            sample_rate = sr
            channels = audio.shape[1]
        elif sr != sample_rate or audio.shape[1] != channels:
            raise ValueError(f"WAV metadata mismatch at {wav_path}")
        chunks.append(audio)
        if index < len(paths) - 1:
            text = source_texts[index].read_text(encoding="utf-8", errors="replace")
            pause_samples = int((_suggest_pause_ms_from_text(text) / 1000.0) * sample_rate)
            if pause_samples > 0:
                chunks.append(np.zeros((pause_samples, channels), dtype=np.float32))
    merged = np.concatenate(chunks, axis=0)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(output_path), merged, sample_rate)


def main() -> int:
    parser = argparse.ArgumentParser(description="Prototype first-run parallel TTS workers on real text chunks.")
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--text-limit", type=int, default=8)
    parser.add_argument("--voice-profile", default="")
    parser.add_argument("--model-key", default="voxcpm_vn")
    parser.add_argument("--inference-timesteps", type=int, default=8)
    parser.add_argument("--baseline-elapsed-s", type=float, default=0)
    parser.add_argument("--scenario", default="parallel_tts_first_run")
    parser.add_argument("--artifact-root", default=str(REPO_ROOT / "benchmarks" / "audio_8x4x"))
    args = parser.parse_args()

    workers = max(1, int(args.workers))
    source_session = REPO_ROOT / "projects_workspace" / "projects" / _safe_slug(args.project_id) / "sessions" / _safe_slug(args.session_id)
    text_files = sorted((source_session / "tts_inputs").glob("*.txt"))
    if args.text_limit > 0:
        text_files = text_files[: args.text_limit]
    if not text_files:
        raise FileNotFoundError(f"No tts_inputs found in {source_session}")

    artifact_dir = _create_artifact_dir(Path(args.artifact_root), f"{args.scenario}_{workers}w_{len(text_files)}chunks")
    _write_json(
        artifact_dir / "input" / "source_manifest.json",
        {
            "project_id": args.project_id,
            "session_id": args.session_id,
            "workers": workers,
            "text_count": len(text_files),
            "texts": [{"name": path.name, "sha256": _sha256_file(path)} for path in text_files],
        },
    )

    groups = _round_robin_split(text_files, workers)
    python_exec = _pick_python()
    procs: list[subprocess.Popen[str]] = []
    started = time.perf_counter()
    worker_reports: list[dict] = []
    all_logs: list[str] = []
    try:
        for worker_index, group in enumerate(groups, start=1):
            text_dir = artifact_dir / "work" / f"worker_{worker_index:02d}" / "text"
            output_dir = artifact_dir / "work" / f"worker_{worker_index:02d}" / "audio"
            text_dir.mkdir(parents=True, exist_ok=True)
            output_dir.mkdir(parents=True, exist_ok=True)
            for source in group:
                shutil.copy2(source, text_dir / source.name)
            proc = _launch_worker(python_exec, artifact_dir / "logs" / f"worker_{worker_index:02d}_stderr.log")
            procs.append(proc)
            payload = {
                "cmd": "synth",
                "project_root": str((TTS_ROOT / "VieNeu-TTS").resolve()),
                "voice_dir": str((TTS_ROOT / "voice").resolve()),
                "text_dir": str(text_dir.resolve()),
                "output_dir": str(output_dir.resolve()),
                "combined_output": str((output_dir / "combined.wav").resolve()),
                "manifest_path": str((output_dir / "manifest.json").resolve()),
                "voice_profile": args.voice_profile,
                "model_key": args.model_key,
                "io_workers": 2,
                "inference_timesteps": args.inference_timesteps,
                "device": "cuda",
                "postprocess": False,
                "anti_leak_trim": True,
                "anti_leak_max_ms": 900,
                "head_pre_roll_ms": 10,
                "tail_keep_ms": 100,
                "cache_enabled": False,
            }
            worker_reports.append({
                "worker": worker_index,
                "text_names": [path.name for path in group],
                "payload": payload,
                "proc": proc,
                "output_dir": output_dir,
            })

        for report in worker_reports:
            report["started_s"] = round(time.perf_counter() - started, 3)
            proc = report["proc"]
            assert proc.stdin is not None
            proc.stdin.write(json.dumps(report["payload"], ensure_ascii=False) + "\n")
            proc.stdin.flush()

        for report in worker_reports:
            worker_started = time.perf_counter()
            reply = _read_worker_reply(report["proc"])
            report["elapsed_s"] = round(time.perf_counter() - worker_started, 3)
            report["ok"] = bool(reply.get("ok"))
            report["logs"] = reply.get("logs", [])
            all_logs.extend(report["logs"])
            if not reply.get("ok"):
                report["error"] = reply.get("error", "unknown")
                raise RuntimeError(f"worker {report['worker']} failed: {report['error']}")
    finally:
        for proc in procs:
            if proc.poll() is None:
                try:
                    _send_worker(proc, {"cmd": "shutdown"})
                except Exception:
                    proc.kill()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()

    elapsed_s = time.perf_counter() - started
    ordered_outputs: list[Path] = []
    for source in text_files:
        found = None
        for report in worker_reports:
            candidate = Path(report["output_dir"]) / f"{source.stem}.wav"
            if candidate.exists():
                found = candidate
                break
        if found is None:
            raise FileNotFoundError(f"Missing output for {source.name}")
        target = artifact_dir / "output" / "chunks" / f"{source.stem}.wav"
        shutil.copy2(found, target)
        ordered_outputs.append(target)
    combined_output = artifact_dir / "output" / "combined.wav"
    _merge_wavs(ordered_outputs, text_files, combined_output)

    baseline = float(args.baseline_elapsed_s)
    multiplier = round(baseline / elapsed_s, 4) if baseline > 0 and elapsed_s > 0 else 0
    report_payload = {
        "success": True,
        "elapsed_s": round(elapsed_s, 3),
        "workers": workers,
        "text_count": len(text_files),
        "combined": _wav_metadata(combined_output),
        "chunks": [_wav_metadata(path) for path in ordered_outputs],
        "worker_reports": [
            {
                key: (str(value) if isinstance(value, Path) else value)
                for key, value in report.items()
                if key not in {"proc", "payload"}
            }
            for report in worker_reports
        ],
        "parsed_worker_logs": _parse_worker_logs(all_logs),
        "target": {
            "baseline_elapsed_s": baseline,
            "multiplier_vs_baseline": multiplier,
            "main_first_run_pass_4x": bool(multiplier >= 4.0),
            "max_elapsed_for_4x_s": round(baseline / 4.0, 3) if baseline > 0 else 0,
        },
        "artifact_dir": str(artifact_dir),
    }
    _write_json(artifact_dir / "reports" / "benchmark.json", report_payload)
    _write_json(artifact_dir / "reports" / "quality.json", {
        "success": True,
        "combined_wav": report_payload["combined"],
        "note": "First-run parallel worker prototype; manual listening still required before production use.",
    })
    _write_text(
        artifact_dir / "reports" / "summary.md",
        "\n".join(
            [
                "# Parallel TTS First-Run Benchmark Summary",
                "",
                f"- Success: `{report_payload['success']}`",
                f"- Workers: `{workers}`",
                f"- Text chunks: `{len(text_files)}`",
                f"- Elapsed seconds: `{report_payload['elapsed_s']}`",
                f"- Baseline seconds: `{baseline}`",
                f"- Multiplier vs baseline: `{multiplier}`",
                f"- Main first-run pass 4x: `{report_payload['target']['main_first_run_pass_4x']}`",
            ]
        )
        + "\n",
    )
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
    except Exception as exc:
        _write_text(artifact_dir / "logs" / "nvidia_smi.txt", str(exc))
    print(json.dumps(report_payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
