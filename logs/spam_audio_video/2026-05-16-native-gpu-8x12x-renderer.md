# 2026-05-16 Native GPU 8x-12x Renderer

Status: historical investigation log. The production renderer was later moved
to `spam_audio_video/renderers/story_gpu_renderer` and became the only video
path in `v0.1.6`.

## Work Completed

- Installed Rust via `winget`.
- Installed Visual Studio Build Tools C++ workload via `winget` so Rust MSVC builds can link.
- Added benchmark artifact folders:
  - `spam_audio_video/benchmarks/render_4k60/`
  - `spam_audio_video/benchmarks/native_gpu_4k60/`
- Updated benchmark script to create timestamped artifact folders with input, output, reports, frames, screenshots, and logs.
- Added render quality comparison tool with metadata checks, sampled frame extraction, SSIM, and PSNR.
- Added native renderer input export for the first prototype branch.
- Scaffolded the first Rust crate that later became `spam_audio_video/renderers/story_gpu_renderer`.
- Moved Cargo target output outside source to `D:/cargo-target/story_gpu_renderer`.
- Removed generated `target/` folder from the source tree.

## Benchmarks

Current FFmpeg artifact:

- Folder: `spam_audio_video/benchmarks/render_4k60/20260516_221957_current_ffmpeg_one_scene_30s/`
- Elapsed: `104.298s`
- Output: 4K60, `h264_nvenc`
- Self quality check: SSIM `1.0`, PSNR `inf`

Native speed-probe artifact:

- Folder: `spam_audio_video/benchmarks/native_gpu_4k60/20260516_223237_native_gpu_speed_probe_one_scene_30s/`
- Elapsed: `25.835s`
- Multiplier vs `102.707s` baseline: `3.9755x`
- 8x target: failed
- 12x target: failed
- Quality gate: failed, SSIM `0.609109`, PSNR `13.960153`

## Decision

The FFmpeg/NVENC pipe speed ceiling is not enough for the requested 8x-12x target. The next phase must implement direct GPU texture-to-NVENC or an equivalent zero-copy encode path before spending more time on full shader parity.

This checkpoint is intentionally not marked as passing.
