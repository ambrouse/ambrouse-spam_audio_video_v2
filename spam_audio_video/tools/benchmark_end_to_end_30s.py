from __future__ import annotations

import argparse
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
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from auto_generate_video import VideoPipeline


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^0-9A-Za-z_.-]+", "_", str(value or "").strip())
    return slug.strip("._") or "run"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _run_command(cmd: list[str], log_path: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    started = time.perf_counter()
    result = subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        check=False,
    )
    elapsed_s = time.perf_counter() - started
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        "\n".join(
            [
                f"command: {' '.join(cmd)}",
                f"returncode: {result.returncode}",
                f"elapsed_s: {elapsed_s:.3f}",
                f"env_overrides: {json.dumps(env or {}, ensure_ascii=False)}" if env else "env_overrides: {}",
                "",
                "STDOUT:",
                result.stdout,
                "",
                "STDERR:",
                result.stderr,
            ]
        ),
        encoding="utf-8",
    )
    if result.returncode != 0:
        raise RuntimeError(f"Command failed, see {log_path}: {' '.join(cmd)}")
    return result


def _latest_child(root: Path) -> Path:
    children = [path for path in root.iterdir() if path.is_dir()]
    if not children:
        raise FileNotFoundError(f"No benchmark artifact directories in {root}")
    return max(children, key=lambda path: path.stat().st_mtime)


def _wav_metadata(path: Path) -> dict:
    if not path.exists():
        return {"exists": False, "path": str(path)}
    with wave.open(str(path), "rb") as handle:
        frames = handle.getnframes()
        rate = handle.getframerate()
        channels = handle.getnchannels()
        width = handle.getsampwidth()
    return {
        "exists": True,
        "path": str(path),
        "size": path.stat().st_size,
        "sample_rate": rate,
        "channels": channels,
        "sample_width_bytes": width,
        "frames": frames,
        "duration_s": round(frames / rate, 3) if rate else 0,
    }


def _probe_media_with_ffmpeg(ffmpeg_bin: str, path: Path) -> dict:
    result = subprocess.run(
        [ffmpeg_bin, "-hide_banner", "-i", str(path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    text = f"{result.stderr}\n{result.stdout}"
    payload: dict = {"path": str(path), "probe": "ffmpeg"}
    duration_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", text)
    if duration_match:
        hours, minutes, seconds = duration_match.groups()
        payload["format"] = {
            "duration": str(int(hours) * 3600 + int(minutes) * 60 + float(seconds)),
            "size": str(path.stat().st_size) if path.exists() else "0",
        }
    streams: list[dict] = []
    video_match = re.search(r"Video:\s*([^,\n]+).*?(\d{3,5})x(\d{3,5}).*?(\d+(?:\.\d+)?)\s*fps", text, flags=re.I | re.S)
    if video_match:
        codec, width, height, fps = video_match.groups()
        streams.append(
            {
                "codec_type": "video",
                "codec_name": codec.strip(),
                "width": int(width),
                "height": int(height),
                "avg_frame_rate": f"{float(fps):g}/1",
                "r_frame_rate": f"{float(fps):g}/1",
            }
        )
    audio_match = re.search(r"Audio:\s*([^,\n]+).*?(\d+)\s*Hz,\s*([^,\n]+)", text, flags=re.I | re.S)
    if audio_match:
        codec, rate, layout = audio_match.groups()
        streams.append(
            {
                "codec_type": "audio",
                "codec_name": codec.strip(),
                "sample_rate": rate,
                "channel_layout": layout.strip(),
            }
        )
    payload["streams"] = streams
    return payload


def _probe_media(ffprobe_bin: str, path: Path, ffmpeg_bin: str | None = None) -> dict:
    cmd = [
        ffprobe_bin,
        "-v",
        "error",
        "-show_entries",
        "format=duration,size,bit_rate:stream=index,codec_type,codec_name,width,height,avg_frame_rate,r_frame_rate,sample_rate,channels,duration,nb_frames",
        "-of",
        "json",
        str(path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    except FileNotFoundError:
        if ffmpeg_bin:
            return _probe_media_with_ffmpeg(ffmpeg_bin, path)
        return {"error": "ffprobe was not found", "path": str(path)}
    if result.returncode != 0:
        if ffmpeg_bin:
            return _probe_media_with_ffmpeg(ffmpeg_bin, path)
        return {"error": result.stderr.strip(), "path": str(path)}
    try:
        payload = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        payload = {"error": "invalid ffprobe json", "stdout": result.stdout[:1000]}
    payload["path"] = str(path)
    return payload


def _build_report_from_artifact(artifact_dir: Path, ffprobe_bin: str, ffmpeg_bin: str, config: dict, started_total: float | None = None) -> dict:
    audio_report_path = artifact_dir / "audio" / "artifact" / "reports" / "benchmark.json"
    video_report_path = artifact_dir / "video" / "artifact" / "reports" / "benchmark.json"
    audio_report = json.loads(audio_report_path.read_text(encoding="utf-8"))
    video_report = json.loads(video_report_path.read_text(encoding="utf-8"))

    final_audio_path = artifact_dir / "final" / "combined.wav"
    final_silent_path = artifact_dir / "final" / "silent_4k60.mp4"
    final_mkv = artifact_dir / "final" / "final_eval_lossless_audio.mkv"
    final_mp4 = artifact_dir / "final" / "final_preview_mp4_aac.mp4"
    silent_probe = _probe_media(ffprobe_bin, final_silent_path, ffmpeg_bin)
    video_streams = [stream for stream in (silent_probe.get("streams") or []) if stream.get("codec_type") == "video"]
    video_stream = video_streams[0] if video_streams else ((silent_probe.get("streams") or [{}])[0] if silent_probe.get("streams") else {})
    audio_meta = _wav_metadata(final_audio_path)

    elapsed_total = (time.perf_counter() - started_total) if started_total else 0
    log_elapsed: dict[str, float] = {}
    if not elapsed_total:
        for log_path in sorted((artifact_dir / "logs").glob("*.log")):
            text = log_path.read_text(encoding="utf-8", errors="replace")
            match = re.search(r"^elapsed_s:\s*([0-9.]+)", text, flags=re.M)
            if match:
                log_elapsed[log_path.stem] = float(match.group(1))
        elapsed_total = sum(log_elapsed.values())
    audio_duration = float(audio_meta.get("duration_s") or 0)
    audio_elapsed = float(audio_report.get("elapsed_s") or 0)
    video_duration = float(video_report.get("video_duration_s") or 0)
    video_elapsed = float(video_report.get("elapsed_s") or 0)
    return {
        "success": all(path.exists() for path in (final_audio_path, final_silent_path, final_mkv, final_mp4)),
        "artifact_dir": str(artifact_dir),
        "elapsed_s": round(elapsed_total, 3) if elapsed_total else None,
        "elapsed_breakdown_s": log_elapsed,
        "config": config,
        "audio": {
            "elapsed_s": audio_elapsed,
            "duration_s": audio_duration,
            "speed_x": round(audio_duration / audio_elapsed, 4) if audio_elapsed > 0 else 0,
            "cache_hits": int((audio_report.get("manifest_cache") or {}).get("hits") or 0),
            "cache_misses": int((audio_report.get("manifest_cache") or {}).get("misses") or 0),
            "combined_wav": audio_meta,
            "benchmark_report": str(audio_report_path),
        },
        "video": {
            "elapsed_s": video_elapsed,
            "duration_s": video_duration,
            "speed_x": round(video_duration / video_elapsed, 4) if video_elapsed > 0 else 0,
            "width": int(video_stream.get("width") or 0),
            "height": int(video_stream.get("height") or 0),
            "fps": video_stream.get("avg_frame_rate") or video_stream.get("r_frame_rate") or "",
            "benchmark_report": str(video_report_path),
        },
        "final_outputs": {
            "audio_wav": str(final_audio_path),
            "silent_video_mp4": str(final_silent_path),
            "mkv_lossless_audio": str(final_mkv),
            "mp4_aac_preview": str(final_mp4),
        },
        "probes": {
            "audio_wav": audio_meta,
            "silent_video": silent_probe,
            "final_mkv": _probe_media(ffprobe_bin, final_mkv, ffmpeg_bin),
            "final_mp4": _probe_media(ffprobe_bin, final_mp4, ffmpeg_bin),
        },
        "screenshots": [str(path) for path in sorted((artifact_dir / "screenshots").glob("*.jpg"))],
    }


def _copytree_contents(src: Path, dst: Path) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    for child in src.iterdir():
        target = dst / child.name
        if child.is_dir():
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(child, target)
        else:
            shutil.copy2(child, target)


def _write_summary(path: Path, report: dict) -> None:
    lines = [
        "# End-to-End 30s Audio + 4K60 Video Benchmark",
        "",
        f"- Success: `{report.get('success')}`",
        f"- Artifact folder: `{report.get('artifact_dir')}`",
        f"- Total elapsed seconds: `{report.get('elapsed_s')}`",
        f"- Audio elapsed seconds: `{report.get('audio', {}).get('elapsed_s')}`",
        f"- Audio duration seconds: `{report.get('audio', {}).get('duration_s')}`",
        f"- Audio speed x: `{report.get('audio', {}).get('speed_x')}`",
        f"- Audio cache hits/misses: `{report.get('audio', {}).get('cache_hits')}/{report.get('audio', {}).get('cache_misses')}`",
        f"- Video elapsed seconds: `{report.get('video', {}).get('elapsed_s')}`",
        f"- Video duration seconds: `{report.get('video', {}).get('duration_s')}`",
        f"- Video speed x: `{report.get('video', {}).get('speed_x')}`",
        f"- Video resolution/FPS: `{report.get('video', {}).get('width')}x{report.get('video', {}).get('height')} @ {report.get('video', {}).get('fps')}`",
        f"- Final lossless-audio preview: `{report.get('final_outputs', {}).get('mkv_lossless_audio')}`",
        f"- Final MP4 preview: `{report.get('final_outputs', {}).get('mp4_aac_preview')}`",
        "",
        "## Notes",
        "",
        "- `final_eval_lossless_audio.mkv` keeps the rendered H.264 video stream and WAV audio as PCM, so it is the best file for judging audio quality without AAC loss.",
        "- `final_preview_mp4_aac.mp4` is only a compatibility preview because MP4 normally stores compressed audio.",
        "- Manual listening/viewing is still required for final style and voice-clone judgment.",
    ]
    _write_text(path, "\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a real near-30s TTS + 4K60 render benchmark and collect one review folder.")
    parser.add_argument("--project-id", default="test-1")
    parser.add_argument("--session-id", default="session_ch0001_to_ch0010")
    parser.add_argument("--text-limit", type=int, default=4)
    parser.add_argument("--voice-profile", default="")
    parser.add_argument("--tts-io-workers", type=int, default=6)
    parser.add_argument("--inference-timesteps", type=int, default=8)
    parser.add_argument("--cache-enabled", action="store_true")
    parser.add_argument("--render-workers", type=int, default=6)
    parser.add_argument("--video-preset", default="quality")
    parser.add_argument("--encoder", default="auto")
    parser.add_argument("--artifact-root", default=str(REPO_ROOT / "benchmarks" / "end_to_end_30s"))
    parser.add_argument("--finalize-existing", default="", help="Only rebuild the summary/report for an existing artifact folder.")
    parser.add_argument("--scenario", default="real_tts_plus_real_4k60")
    args = parser.parse_args()

    pipeline = VideoPipeline(REPO_ROOT)
    ffmpeg_bin = pipeline.ffmpeg_bin
    ffprobe_bin = str(Path(ffmpeg_bin).with_name("ffprobe.exe" if sys.platform.startswith("win") else "ffprobe"))
    if not Path(ffprobe_bin).exists():
        ffprobe_bin = "ffprobe"

    base_config = {
        "project_id": args.project_id,
        "session_id": args.session_id,
        "text_limit": args.text_limit,
        "cache_enabled": bool(args.cache_enabled),
        "render_workers": args.render_workers,
        "video_preset": args.video_preset,
        "encoder": args.encoder,
    }

    if args.finalize_existing:
        artifact_dir = Path(args.finalize_existing)
        report = _build_report_from_artifact(artifact_dir, ffprobe_bin, ffmpeg_bin, base_config)
        _write_json(artifact_dir / "reports" / "benchmark.json", report)
        _write_summary(artifact_dir / "reports" / "summary.md", report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report.get("success") else 1

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    artifact_dir = Path(args.artifact_root) / f"{stamp}_{_safe_slug(args.scenario)}"
    for child in ("audio", "video", "final", "reports", "logs", "screenshots"):
        (artifact_dir / child).mkdir(parents=True, exist_ok=True)

    started_total = time.perf_counter()

    audio_root = artifact_dir / "audio" / "run"
    audio_cmd = [
        sys.executable,
        str(REPO_ROOT / "tools" / "benchmark_tts_pipeline.py"),
        "--project-id",
        args.project_id,
        "--session-id",
        args.session_id,
        "--text-limit",
        str(args.text_limit),
        "--tts-io-workers",
        str(args.tts_io_workers),
        "--inference-timesteps",
        str(args.inference_timesteps),
        "--scenario",
        "audio_for_e2e_30s",
        "--artifact-root",
        str(audio_root),
    ]
    if args.voice_profile:
        audio_cmd.extend(["--voice-profile", args.voice_profile])
    if args.cache_enabled:
        audio_cmd.append("--cache-enabled")
    else:
        audio_cmd.append("--no-cache")
    _run_command(audio_cmd, artifact_dir / "logs" / "audio_benchmark_command.log")
    audio_artifact = _latest_child(audio_root)
    _copytree_contents(audio_artifact, artifact_dir / "audio" / "artifact")
    audio_report = json.loads((audio_artifact / "reports" / "benchmark.json").read_text(encoding="utf-8"))
    source_audio_path = Path(audio_report["audio"]["combined"]["path"])
    final_audio_path = artifact_dir / "final" / "combined.wav"
    shutil.copy2(source_audio_path, final_audio_path)
    audio_meta = _wav_metadata(final_audio_path)
    render_duration_s = float(audio_meta.get("duration_s") or 30.0)

    video_root = artifact_dir / "video" / "run"
    video_output_name = f"e2e_4k60_{stamp}.mp4"
    video_cmd = [
        sys.executable,
        str(REPO_ROOT / "tools" / "benchmark_4k60_render.py"),
        "--project-id",
        args.project_id,
        "--session-id",
        args.session_id,
        "--scenes",
        "1",
        "--seconds-per-image",
        f"{render_duration_s:.3f}",
        "--encoder",
        args.encoder,
        "--video-preset",
        args.video_preset,
        "--render-workers",
        str(args.render_workers),
        "--output-name",
        video_output_name,
        "--artifact-renderer",
        "current_ffmpeg",
        "--scenario",
        "video_for_e2e_30s",
        "--artifact-root",
        str(video_root),
    ]
    video_env = os.environ.copy()
    video_env["SPAM_VIDEO_NATIVE_AUDIO_PATH"] = str(final_audio_path)
    _run_command(video_cmd, artifact_dir / "logs" / "video_benchmark_command.log", env=video_env)
    video_artifact = _latest_child(video_root)
    _copytree_contents(video_artifact, artifact_dir / "video" / "artifact")
    video_report = json.loads((video_artifact / "reports" / "benchmark.json").read_text(encoding="utf-8"))
    source_video_path = Path(video_report["output_path"])
    final_silent_path = artifact_dir / "final" / "silent_4k60.mp4"
    shutil.copy2(source_video_path, final_silent_path)

    final_mkv = artifact_dir / "final" / "final_eval_lossless_audio.mkv"
    mux_mkv_cmd = [
        ffmpeg_bin,
        "-hide_banner",
        "-y",
        "-i",
        str(final_silent_path),
        "-i",
        str(final_audio_path),
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c:v",
        "copy",
        "-c:a",
        "pcm_s16le",
        "-shortest",
        str(final_mkv),
    ]
    _run_command(mux_mkv_cmd, artifact_dir / "logs" / "mux_lossless_mkv.log")

    final_mp4 = artifact_dir / "final" / "final_preview_mp4_aac.mp4"
    mux_mp4_cmd = [
        ffmpeg_bin,
        "-hide_banner",
        "-y",
        "-i",
        str(final_silent_path),
        "-i",
        str(final_audio_path),
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-shortest",
        str(final_mp4),
    ]
    _run_command(mux_mp4_cmd, artifact_dir / "logs" / "mux_mp4_preview.log")

    for second in (5, min(20, max(1, int(render_duration_s) - 2))):
        screenshot = artifact_dir / "screenshots" / f"frame_{second:02d}s.jpg"
        frame_cmd = [
            ffmpeg_bin,
            "-hide_banner",
            "-y",
            "-ss",
            str(second),
            "-i",
            str(final_mkv),
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(screenshot),
        ]
        _run_command(frame_cmd, artifact_dir / "logs" / f"extract_frame_{second:02d}s.log")

    elapsed_total = time.perf_counter() - started_total
    audio_duration = float(audio_meta.get("duration_s") or 0)
    audio_elapsed = float(audio_report.get("elapsed_s") or 0)
    video_duration = float(video_report.get("video_duration_s") or 0)
    video_elapsed = float(video_report.get("elapsed_s") or 0)
    report = _build_report_from_artifact(artifact_dir, ffprobe_bin, ffmpeg_bin, base_config, started_total=started_total)
    report["elapsed_s"] = round(elapsed_total, 3)
    _write_json(artifact_dir / "reports" / "benchmark.json", report)
    _write_summary(artifact_dir / "reports" / "summary.md", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
