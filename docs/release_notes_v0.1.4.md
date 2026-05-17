# Release Notes - v0.1.4

## Highlights

- Promoted the Rust/D3D11/NVENC story renderer into the main video pipeline for
  16:9 `60fps` H.264/NVENC outputs.
- Kept FFmpeg as the automatic fallback when the native renderer is unavailable
  or the output contract is unsupported.
- Packaged `story_gpu_renderer.exe` into the Windows portable release so fresh
  machines can use the native path without installing Rust.
- Improved the native audio visualizer layout so it draws as two separated
  left/right clusters.
- Added per-clip `audio_start_seconds` so multi-clip native renders sample the
  correct audio segment for visualizer bars.
- Added benchmark CLI controls for width, height, FPS, and audio mux testing.

## Validation

Local validation on 2026-05-17:

| Check | Result |
| --- | --- |
| Shell setup syntax checks | Pass |
| Python compile for video pipeline, backend, TTS worker, and benchmark tool | Pass |
| Frontend JavaScript syntax check | Pass |
| Unit tests | Pass, 2 tests |
| Rust `cargo fmt --check` and release tests | Pass |
| Source setup install-only validation | Pass |
| Native HD60 pipeline smoke render | Pass: 720p60 5s in `1.539s`, native path used |
| Native 4K60 pipeline smoke render with audio | Pass: 4K60 5s in `7.831s`, native path used |
| Portable zip build with native renderer binary | Pass: `dist/ambrouse-studio-v0.1.4-win64.zip` |
| Extracted portable native probe | Pass: D3D11 device and NVENC session opened |

## Runtime Notes

- Native renderer auto-selects for 16:9 `60fps` `h264_nvenc` outputs.
- Set `SPAM_VIDEO_NATIVE_GPU_RENDER=off` to force FFmpeg fallback.
- Set `SPAM_VIDEO_NATIVE_GPU_RENDER=force` to fail loudly if native cannot run.

## Known Limits

- The native path intentionally targets visual equivalence accepted by review,
  not pixel-identical FFmpeg SSIM parity.
- Full offline model bundling is still not included; target machines need
  model/cache downloads unless a separate offline bundle is prepared.
