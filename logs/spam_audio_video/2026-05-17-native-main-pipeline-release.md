# 2026-05-17 Native Main Pipeline Release

Status: superseded by `v0.1.6`, where the accepted Rust/D3D11/NVENC story
renderer became the only production video path and the old fallback/clip cache
contract was removed.

## Scope

- Move the accepted Rust/D3D11/NVENC renderer into the main video pipeline.
- Clean benchmark/test artifacts before release.
- Build and validate a portable release for fresh Windows machines.

## Code Changes

- `VideoPipeline.render_video(...)` selected the native renderer
  automatically for 16:9 `60fps` `h264_nvenc` outputs in this release.
- This fallback-based contract was removed in `v0.1.6`; production now fails
  fast unless the Rust/D3D11/NVENC story renderer can run.
- Native clip cache folders included resolution/FPS and audio-visualizer state
  in this historical release. The clip cache path was removed in `v0.1.6`.
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
- Current native binary is packaged from
  `spam_audio_video/renderers/story_gpu_renderer/target/release/story_gpu_renderer.exe`.
