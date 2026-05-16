# 2026-05-17 Native Renderer Optimization Loop

## Goal
- Continue optimizing until video `>8x` and audio `>4x`, preserving output quality/style/effects.
- Do not count cache-hit audio as first-run TTS pass.

## FFmpeg Optimization Probes
- Static layer cache was implemented behind `SPAM_VIDEO_STATIC_LAYER_CACHE=1`.
  - First 30s 4K60 run: `117.916s`.
  - Cache-warm 30s 4K60 run: `110.784s`.
  - Baseline current FFmpeg: about `104.298s`.
  - Result: failed; left disabled by default.
- Single-scene fused overlay was implemented behind `SPAM_VIDEO_FUSE_SINGLE_SCENE_OVERLAY=1`.
  - 5s smoke: `35.179s`.
  - Result: failed; left disabled by default.
- Explicit FFmpeg filter threading was implemented behind `SPAM_FFMPEG_FILTER_THREADS`.
  - 5s smoke with 12 threads: `19.354s`.
  - Result: failed; left disabled by default.
- Default-after-probes 5s smoke still renders successfully at 3840x2160/60fps.

## Native Renderer Progress
- Rust/MSVC toolchain is available via absolute paths:
  - `C:\Users\LymI\.cargo\bin\cargo.exe`
  - MSVC linker under Visual Studio BuildTools.
- Added native probe command to `story_gpu_renderer`.
- Probe artifacts:
  - `spam_audio_video/benchmarks/native_gpu_4k60/20260517_native_nvenc_probe/report.json`
  - `spam_audio_video/benchmarks/native_gpu_4k60/20260517_native_nvenc_d3d11_probe/report.json`
  - `spam_audio_video/benchmarks/native_gpu_4k60/20260517_native_nvenc_d3d11_session_probe/report.json`
- Latest native probe result:
  - NVENC DLL loaded directly from `C:\Windows\System32\nvEncodeAPI64.dll`.
  - Driver max NVENC API: `13.0`.
  - D3D11 hardware device created.
  - NVENC D3D11 encode session opened and closed successfully in `180ms`.

## Current Status
- FFmpeg filter-level optimization is not enough and should not be the main path.
- Direct D3D11 + NVENC is confirmed viable on this machine.
- Next implementation step is native H.264 initialization, D3D11 texture allocation, shader/image upload, and bitstream output.

## Encode Ceiling Check
- Added `story_gpu_renderer encode-ceiling` using D3D11 texture input and direct NVENC H.264 raw bitstream output.
- Rust build passed after adding the native encode command.
- D3D11 + NVENC smoke results:
  - ARGB 4K60 5s: `2.3801x`.
  - NV12 4K60 5s: `2.5014x`.
- FFmpeg encode-only color-source matrix, 4K60 10s:
  - best H.264: `3.5173x` with `h264_nvenc p1 constqp18`;
  - best HEVC: `3.7665x` with `hevc_nvenc p1 constqp18`;
  - AV1 NVENC failed on this machine.
- This is an encode-only ceiling, before production crop/blur/particles/logo/audio-bar work. It means the requested video `>8x` target cannot be honestly passed on this hardware while encoding every 4K60 frame with the available GPU encoder.

## Real Pipeline Integration Attempt
- Wired the fastest measured NVENC profile into the real production pipeline as `video_preset=throughput`.
- Real 30s 4K60 production run:
  - `throughput`: `104.088s`, `0.2882x`;
  - quality gate failed: SSIM `0.991078` below `0.995`.
- Tried `p2`/VBR-HQ profile:
  - `107.122s`, `0.2801x`;
  - slower than the production quality preset.
- Restored production defaults to `quality` to preserve output.
- Added production stage timings to `render_manifest.json`.
- Final safe production 30s video:
  - `104.490s`, `0.2871x`;
  - SSIM `1.0`, PSNR `inf`;
  - clip/camera/background `58.186s`;
  - visual overlay particles/logo `46.023s`.
- Final first-run audio benchmark:
  - cache `0/4`;
  - `34.646s` audio in `41.101s`;
  - speed `0.8429x`.
