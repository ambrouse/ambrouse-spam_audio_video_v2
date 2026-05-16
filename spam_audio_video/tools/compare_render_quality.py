from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from auto_generate_video import VideoPipeline


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _run(cmd: list[str], timeout_s: int = 300, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_s,
        check=False,
    )


def _ffmpeg_bin() -> str:
    return VideoPipeline(REPO_ROOT).ffmpeg_bin


def _probe(ffmpeg_bin: str, path: Path) -> dict:
    result = _run([ffmpeg_bin, "-hide_banner", "-i", str(path)], timeout_s=60)
    text = f"{result.stderr}\n{result.stdout}"
    duration = 0.0
    duration_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", text)
    if duration_match:
        hours, minutes, seconds = duration_match.groups()
        duration = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    video_match = re.search(r"Video:\s*([^,\n]+).*?(\d{3,5})x(\d{3,5}).*?(\d+(?:\.\d+)?)\s*fps", text, flags=re.I | re.S)
    stream = {"duration": duration}
    if video_match:
        codec, width, height, fps = video_match.groups()
        stream.update({
            "codec_name": codec.strip(),
            "width": int(width),
            "height": int(height),
            "fps": float(fps),
        })
    return {"stream": stream, "raw": text[:4000]}


def _sample_timestamps(duration_s: float, sample_count: int) -> list[float]:
    if duration_s <= 0:
        return [0.0]
    if sample_count <= 1:
        return [max(0.0, duration_s * 0.5)]
    positions = [0.0, 0.10, 0.25, 0.50, 0.75, 0.90, 0.98]
    values = [min(duration_s - (1 / 60), max(0.0, duration_s * pos)) for pos in positions[:sample_count]]
    return values


def _extract_frames(ffmpeg_bin: str, video: Path, target_dir: Path, prefix: str, timestamps: list[float]) -> list[str]:
    target_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[str] = []
    for idx, stamp in enumerate(timestamps, start=1):
        output = target_dir / f"{prefix}_{idx:02d}_{stamp:.3f}s.png"
        result = _run([
            ffmpeg_bin,
            "-y",
            "-ss",
            f"{stamp:.3f}",
            "-i",
            str(video),
            "-frames:v",
            "1",
            str(output),
        ], timeout_s=120)
        if result.returncode == 0 and output.exists():
            outputs.append(str(output))
    return outputs


def _run_metrics(ffmpeg_bin: str, baseline: Path, candidate: Path, report_dir: Path) -> dict:
    ssim_log = report_dir / "ssim.log"
    psnr_log = report_dir / "psnr.log"
    ssim_result = _run([
        ffmpeg_bin,
        "-i",
        str(candidate),
        "-i",
        str(baseline),
        "-lavfi",
        "ssim=stats_file=ssim.log",
        "-f",
        "null",
        "-",
    ], timeout_s=900, cwd=report_dir)
    psnr_result = _run([
        ffmpeg_bin,
        "-i",
        str(candidate),
        "-i",
        str(baseline),
        "-lavfi",
        "psnr=stats_file=psnr.log",
        "-f",
        "null",
        "-",
    ], timeout_s=900, cwd=report_dir)
    text = f"{ssim_result.stderr}\n{ssim_result.stdout}\n{psnr_result.stderr}\n{psnr_result.stdout}"
    ssim_match = re.findall(r"All:([0-9.]+)", text)
    psnr_match = re.findall(r"average:([0-9.]+|inf)", text)
    psnr_value = psnr_match[-1] if psnr_match else ""
    return {
        "returncode": 0 if ssim_result.returncode == 0 and psnr_result.returncode == 0 else 1,
        "ssim_returncode": ssim_result.returncode,
        "psnr_returncode": psnr_result.returncode,
        "ssim_all": float(ssim_match[-1]) if ssim_match else 0.0,
        "psnr_average": float(psnr_value) if psnr_value not in {"", "inf"} else psnr_value,
        "stderr_tail": text[-4000:],
        "ssim_log": str(ssim_log),
        "psnr_log": str(psnr_log),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare 4K60 renderer quality and write benchmark artifact reports.")
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--artifact-dir", required=True)
    parser.add_argument("--sample-count", type=int, default=7)
    parser.add_argument("--skip-metrics", action="store_true")
    parser.add_argument("--min-ssim", type=float, default=0.995)
    parser.add_argument("--min-psnr", type=float, default=42.0)
    args = parser.parse_args()

    baseline = Path(args.baseline).resolve()
    candidate = Path(args.candidate).resolve()
    artifact_dir = Path(args.artifact_dir).resolve()
    report_dir = artifact_dir / "reports"
    frame_current = artifact_dir / "frames" / "current"
    frame_native = artifact_dir / "frames" / "native"
    ffmpeg_bin = _ffmpeg_bin()

    baseline_probe = _probe(ffmpeg_bin, baseline)
    candidate_probe = _probe(ffmpeg_bin, candidate)
    baseline_stream = baseline_probe.get("stream", {})
    candidate_stream = candidate_probe.get("stream", {})
    duration = float(candidate_stream.get("duration") or baseline_stream.get("duration") or 0.0)
    timestamps = _sample_timestamps(duration, max(1, int(args.sample_count)))
    baseline_frames = _extract_frames(ffmpeg_bin, baseline, frame_current, "baseline", timestamps)
    candidate_frames = _extract_frames(ffmpeg_bin, candidate, frame_native, "candidate", timestamps)

    metadata_checks = {
        "width_match": baseline_stream.get("width") == candidate_stream.get("width") == 3840,
        "height_match": baseline_stream.get("height") == candidate_stream.get("height") == 2160,
        "fps_match": abs(float(baseline_stream.get("fps") or 0) - float(candidate_stream.get("fps") or 0)) < 0.01,
        "duration_delta_s": abs(float(baseline_stream.get("duration") or 0) - float(candidate_stream.get("duration") or 0)),
    }
    metrics = {"skipped": True}
    if not args.skip_metrics:
        metrics = _run_metrics(ffmpeg_bin, baseline, candidate, report_dir)

    psnr = metrics.get("psnr_average")
    psnr_pass = True if args.skip_metrics else (psnr == "inf" or float(psnr or 0) >= args.min_psnr)
    ssim_pass = True if args.skip_metrics else float(metrics.get("ssim_all") or 0) >= args.min_ssim
    success = all(bool(v) for k, v in metadata_checks.items() if k != "duration_delta_s")
    success = success and float(metadata_checks["duration_delta_s"]) <= (1 / 60)
    success = success and ssim_pass and psnr_pass

    report = {
        "success": bool(success),
        "baseline": str(baseline),
        "candidate": str(candidate),
        "baseline_probe": baseline_probe,
        "candidate_probe": candidate_probe,
        "metadata_checks": metadata_checks,
        "metrics": metrics,
        "sample_timestamps": timestamps,
        "baseline_frames": baseline_frames,
        "candidate_frames": candidate_frames,
        "thresholds": {
            "min_ssim": args.min_ssim,
            "min_psnr": args.min_psnr,
            "max_duration_delta_s": 1 / 60,
        },
    }
    _write_json(report_dir / "quality.json", report)
    _write_json(report_dir / "ffprobe_current.json", baseline_probe)
    _write_json(report_dir / "ffprobe_native.json", candidate_probe)
    _write_text(
        report_dir / "quality_summary.md",
        "\n".join([
            "# Render Quality Summary",
            "",
            f"- Success: `{success}`",
            f"- SSIM: `{metrics.get('ssim_all')}`",
            f"- PSNR: `{metrics.get('psnr_average')}`",
            f"- Duration delta: `{metadata_checks['duration_delta_s']}`",
            f"- Baseline frames: `{len(baseline_frames)}`",
            f"- Candidate frames: `{len(candidate_frames)}`",
        ]) + "\n",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
