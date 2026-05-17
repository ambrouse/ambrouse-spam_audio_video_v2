# 2026-05-17 Native Main Pipeline Release

## Scope

- Move the accepted Rust/D3D11/NVENC renderer into the main video pipeline.
- Clean benchmark/test artifacts before release.
- Build and validate a portable release for fresh Windows machines.

## Code Changes

- `VideoPipeline.render_video(...)` now selects the native renderer
  automatically for 16:9 `60fps` `h264_nvenc` outputs.
- FFmpeg remains available as fallback when native is disabled, unavailable, or
  the output contract is unsupported.
- Native clip cache folders include resolution/FPS and audio-visualizer state to
  prevent stale clip reuse.
- Native renderer input now carries `audio_start_seconds` for correct
  per-clip audio visualizer timing.
- Native audio visualizer bars are wider separated into left/right clusters.
- Portable release builder now packages `story_gpu_renderer.exe` inside the zip.

## Cleanup

- Removed local benchmark artifacts generated during renderer review:
  `native_gpu_visual_check`, `render_4k60`, `render_hd`, and temporary
  setup-validation folders.
- Removed generated review outputs and native clip caches from the `test-1`
  session workspace.

## Validation

| Check | Result |
| --- | --- |
| `bash -n` setup scripts | Pass |
| Targeted Python compile | Pass |
| `node --check source_full/frontend/app.js` | Pass |
| Python unit tests | Pass, 2 tests |
| `cargo fmt --check` + `cargo test --release` | Pass |
| `setup.sh --install-only --yes --skip-production-validation` | Pass |
| Native 720p60 5s pipeline smoke | Pass: `1.539s`, native path used |
| Native 4K60 5s pipeline smoke with audio | Pass: `7.831s`, native path used |
| Portable zip build | Pass: `dist/ambrouse-studio-v0.1.4-win64.zip` |
| Extracted release native probe | Pass: D3D11 device created, NVENC D3D11 session opened |

## Release Notes

- Release asset: `dist/ambrouse-studio-v0.1.4-win64.zip`.
- Extracted validation folder: `dist/release_validate_v014`.
- Native binary is packaged at
  `spam_audio_video/native_renderers/story_gpu_renderer/target/release/story_gpu_renderer.exe`.
