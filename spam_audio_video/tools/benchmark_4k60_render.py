from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from auto_generate_video import VideoPipeline, VideoPipelineConfig


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^0-9A-Za-z_.-]+", "_", str(value or "").strip())
    return slug.strip("._") or "run"


def _create_artifact_dir(root: Path, renderer: str, scenario: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    artifact_dir = root / f"{stamp}_{_safe_slug(renderer)}_{_safe_slug(scenario)}"
    for child in (
        "input",
        "output",
        "reports",
        "frames/current",
        "frames/native",
        "frames/diff",
        "screenshots",
        "logs",
    ):
        (artifact_dir / child).mkdir(parents=True, exist_ok=True)
    return artifact_dir


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _ffprobe_json(ffprobe_bin: str, video_path: Path, ffmpeg_bin: str | None = None) -> dict:
    cmd = [
        ffprobe_bin,
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height,r_frame_rate,avg_frame_rate,duration,nb_frames,codec_name",
        "-of",
        "json",
        str(video_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        return _ffmpeg_probe_json(ffmpeg_bin or "ffmpeg", video_path)
    if result.returncode != 0:
        return {"error": result.stderr.strip()}
    try:
        return json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        return {"error": "ffprobe returned invalid JSON", "stdout": result.stdout[:1000]}


def _ffmpeg_probe_json(ffmpeg_bin: str, video_path: Path) -> dict:
    try:
        result = subprocess.run(
            [ffmpeg_bin, "-hide_banner", "-i", str(video_path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except FileNotFoundError:
        return {"error": "ffprobe and ffmpeg probe binaries were not found"}
    text = f"{result.stderr or ''}\n{result.stdout or ''}"
    duration_s = 0.0
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", text)
    if match:
        hours, minutes, seconds = match.groups()
        duration_s = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    video_match = re.search(r"Video:\s*([^,\n]+).*?(\d{3,5})x(\d{3,5}).*?(\d+(?:\.\d+)?)\s*fps", text, flags=re.I | re.S)
    stream = {"duration": duration_s}
    if video_match:
        codec, width, height, fps = video_match.groups()
        stream.update({
            "codec_name": codec.strip(),
            "width": int(width),
            "height": int(height),
            "avg_frame_rate": f"{float(fps):g}/1",
            "r_frame_rate": f"{float(fps):g}/1",
        })
    return {"streams": [stream], "probe": "ffmpeg"}


def _write_limited_analysis(pipeline: VideoPipeline, project_id: str, session_id: str, seconds_per_image: float, scenes: int) -> tuple[Path, str | None]:
    dirs = pipeline.ensure_session_video_dirs(project_id, session_id)
    manifest_path = dirs["manifests_dir"] / "analysis_manifest.json"
    original = manifest_path.read_text(encoding="utf-8") if manifest_path.exists() else None
    manifest = pipeline.analyze_session(
        project_id,
        session_id,
        scene_duration_seconds=seconds_per_image,
        image_count_limit=max(1, int(scenes)),
        prompt_tts_input_limit=max(1, int(scenes)),
    )
    manifest["total_audio_seconds"] = round(max(1, int(scenes)) * float(seconds_per_image), 3)
    manifest["benchmark_override"] = {
        "scenes": max(1, int(scenes)),
        "seconds_per_image": float(seconds_per_image),
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest_path, original


def _source_manifest(pipeline: VideoPipeline, project_id: str, session_id: str) -> dict:
    dirs = pipeline.ensure_session_video_dirs(project_id, session_id)
    images = sorted(p for p in dirs["images_dir"].glob("scene_*.png") if p.is_file())
    audio_path = dirs["session_dir"] / "audio" / "combined.wav"
    tts_files = sorted(p for p in (dirs["session_dir"] / "tts_inputs").glob("text_*.txt") if p.is_file())
    return {
        "project_id": project_id,
        "session_id": session_id,
        "session_dir": str(dirs["session_dir"]),
        "audio": {
            "path": str(audio_path),
            "exists": audio_path.exists(),
            "size": audio_path.stat().st_size if audio_path.exists() else 0,
        },
        "images": [
            {"path": str(path), "size": path.stat().st_size}
            for path in images
        ],
        "tts_inputs": {
            "count": len(tts_files),
            "sample": [path.name for path in tts_files[:5]],
        },
    }


def _write_summary(path: Path, report: dict, target_baseline_s: float) -> None:
    elapsed = float(report.get("elapsed_s") or 0)
    multiplier = round(target_baseline_s / elapsed, 4) if elapsed > 0 else 0
    passed_8x = multiplier >= 8.0
    passed_12x = multiplier >= 12.0
    lines = [
        "# 4K60 Render Benchmark Summary",
        "",
        f"- Success: `{bool(report.get('success'))}`",
        f"- Output: `{report.get('output_path')}`",
        f"- Elapsed seconds: `{report.get('elapsed_s')}`",
        f"- Video duration seconds: `{report.get('video_duration_s')}`",
        f"- Render speed x: `{report.get('render_speed_x')}`",
        f"- Baseline seconds: `{target_baseline_s}`",
        f"- Multiplier vs baseline: `{multiplier}`",
        f"- Pass 8x target: `{passed_8x}`",
        f"- Pass 12x target: `{passed_12x}`",
        f"- Encoder: `{report.get('render_manifest', {}).get('video_encoder', '')}`",
        f"- GPU fallback used: `{report.get('render_manifest', {}).get('gpu_fallback_used', '')}`",
    ]
    _write_text(path, "\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark the real 4K60 video render path on an existing project/session.")
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--scenes", type=int, default=2)
    parser.add_argument("--seconds-per-image", type=float, default=30.0)
    parser.add_argument("--encoder", default="auto")
    parser.add_argument("--video-preset", default="quality")
    parser.add_argument("--render-workers", type=int, default=6)
    parser.add_argument("--output-name", default="")
    parser.add_argument("--report-path", default="")
    parser.add_argument("--artifact-root", default=str(REPO_ROOT / "benchmarks" / "render_4k60"))
    parser.add_argument("--artifact-renderer", default="current_ffmpeg")
    parser.add_argument("--scenario", default="one_scene_30s")
    parser.add_argument("--baseline-elapsed-s", type=float, default=102.707)
    parser.add_argument("--no-artifacts", action="store_true")
    args = parser.parse_args()

    pipeline = VideoPipeline(REPO_ROOT)
    artifact_dir: Path | None = None
    if not args.no_artifacts:
        artifact_dir = _create_artifact_dir(Path(args.artifact_root), args.artifact_renderer, args.scenario)
        _write_json(artifact_dir / "input" / "source_manifest.json", _source_manifest(pipeline, args.project_id, args.session_id))
    output_name = args.output_name or f"benchmark_4k60_{int(time.time())}.mp4"
    manifest_path, original_manifest = _write_limited_analysis(
        pipeline,
        args.project_id,
        args.session_id,
        args.seconds_per_image,
        args.scenes,
    )
    cfg = VideoPipelineConfig(
        scene_duration_seconds=args.seconds_per_image,
        width=3840,
        height=2160,
        fps=60,
        video_encoder=args.encoder,
        video_preset=args.video_preset,
        video_crf=18,
        video_cq=18,
        render_workers=max(1, int(args.render_workers)),
    )
    if artifact_dir:
        renderer_input = pipeline.build_native_renderer_input(
            args.project_id,
            args.session_id,
            cfg,
            artifact_dir / "output" / f"{_safe_slug(args.artifact_renderer)}.mp4",
        )
        _write_json(artifact_dir / "input" / "renderer_input.json", renderer_input)

    started = time.perf_counter()
    result: dict = {}
    try:
        result = pipeline.render_video(
            args.project_id,
            args.session_id,
            cfg,
            output_name=output_name,
            render_with_audio=False,
        )
    finally:
        if original_manifest is None:
            manifest_path.unlink(missing_ok=True)
        else:
            manifest_path.write_text(original_manifest, encoding="utf-8")
    elapsed_s = time.perf_counter() - started

    video_rel = str(result.get("render_path") or result.get("video_path") or result.get("session_video_path") or "")
    if not video_rel:
        raise RuntimeError(f"Render result did not include a video path: {result}")
    video_path = REPO_ROOT / video_rel
    ffprobe_bin = str(Path(pipeline.ffmpeg_bin).with_name("ffprobe.exe" if sys.platform.startswith("win") else "ffprobe"))
    if not Path(ffprobe_bin).exists():
        ffprobe_bin = "ffprobe"
    probe = _ffprobe_json(ffprobe_bin, video_path, pipeline.ffmpeg_bin)
    duration_s = 0.0
    streams = probe.get("streams") if isinstance(probe, dict) else None
    if isinstance(streams, list) and streams:
        try:
            duration_s = float(streams[0].get("duration") or 0)
        except Exception:
            duration_s = 0.0

    report = {
        "success": True,
        "project_id": args.project_id,
        "session_id": args.session_id,
        "output_path": str(video_path),
        "elapsed_s": round(elapsed_s, 3),
        "video_duration_s": round(duration_s, 3),
        "render_speed_x": round(duration_s / elapsed_s, 4) if elapsed_s > 0 and duration_s > 0 else 0,
        "config": {
            "width": cfg.width,
            "height": cfg.height,
            "fps": cfg.fps,
            "seconds_per_image": cfg.scene_duration_seconds,
            "encoder": cfg.video_encoder,
            "video_preset": cfg.video_preset,
            "render_workers": cfg.render_workers,
            "scenes": args.scenes,
        },
        "render_manifest": result,
        "ffprobe": probe,
        "artifact_dir": str(artifact_dir) if artifact_dir else "",
        "target": {
            "baseline_elapsed_s": float(args.baseline_elapsed_s),
            "multiplier_vs_baseline": round(float(args.baseline_elapsed_s) / elapsed_s, 4) if elapsed_s > 0 else 0,
            "pass_8x": bool(elapsed_s > 0 and float(args.baseline_elapsed_s) / elapsed_s >= 8.0),
            "pass_12x": bool(elapsed_s > 0 and float(args.baseline_elapsed_s) / elapsed_s >= 12.0),
            "max_elapsed_for_8x_s": round(float(args.baseline_elapsed_s) / 8.0, 3),
            "max_elapsed_for_12x_s": round(float(args.baseline_elapsed_s) / 12.0, 3),
        },
    }
    report_path = Path(args.report_path) if args.report_path else video_path.with_suffix(".benchmark.json")
    if not report_path.is_absolute():
        report_path = REPO_ROOT / report_path
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report["report_path"] = str(report_path)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if artifact_dir:
        output_name = "current_ffmpeg.mp4" if args.artifact_renderer == "current_ffmpeg" else f"{_safe_slug(args.artifact_renderer)}.mp4"
        artifact_video_path = artifact_dir / "output" / output_name
        shutil.copy2(video_path, artifact_video_path)
        _write_json(artifact_dir / "reports" / "benchmark.json", report)
        _write_json(artifact_dir / "reports" / f"ffprobe_{_safe_slug(args.artifact_renderer)}.json", probe)
        _write_json(artifact_dir / "reports" / "renderer_report.json", result)
        _write_json(artifact_dir / "reports" / "quality.json", {"success": None, "message": "Quality comparison not run by benchmark_4k60_render.py."})
        _write_summary(artifact_dir / "reports" / "summary.md", report, float(args.baseline_elapsed_s))
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
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
