# Native Renderer 8x Loop - 2026-05-17

## Decision

The remaining viable path for the video target is a native GPU renderer:

- D3D11 textures for scene/image layers;
- shader-based crop, motion, particles, and logo overlay;
- direct NVENC encode session;
- FFmpeg only for final audio mux.

## Evidence

Small FFmpeg-side probes did not improve the production render:

- static layer cache: slower than baseline;
- fused single-scene overlay: slower on a 5s smoke;
- explicit FFmpeg filter threading: slower on a 5s smoke.

The current FFmpeg filter graph remains CPU/filter bound and is not a credible path to `>8x`.

## Native Checkpoint

`story_gpu_renderer probe-native` now validates the real native path:

- loads `nvEncodeAPI64.dll`;
- reads NVENC max supported API version;
- creates a D3D11 hardware device;
- opens and closes an NVENC D3D11 encode session.

Latest report:

```text
spam_audio_video/benchmarks/native_gpu_4k60/20260517_native_nvenc_d3d11_session_probe/report.json
```

## Next Engineering Step

Implement the native encoder loop:

1. initialize H.264 NVENC parameters matching the current output constraints;
2. allocate D3D11 BGRA/NV12 textures;
3. submit a solid-color and then image-backed texture sequence;
4. write Annex B/MP4-compatible bitstream artifact;
5. only then port visual shader parity.

## Encode Ceiling Result

The native encoder loop now exists as `story_gpu_renderer encode-ceiling`.

Measured ceiling on this machine:

- direct D3D11 ARGB texture to NVENC H.264, 4K60 5s: `2.3801x`;
- direct D3D11 NV12 texture to NVENC H.264, 4K60 5s: `2.5014x`;
- FFmpeg encode-only color-source best H.264, 4K60 10s: `3.5173x`;
- FFmpeg encode-only color-source best HEVC, 4K60 10s: `3.7665x`;
- AV1 NVENC is not usable here.

This proves the current machine cannot reach the requested `>8x` video target by software changes alone when every 4K60 frame must be encoded. A native shader renderer is still useful to remove CPU-filter overhead, but it will be capped below the target by the hardware encoder.

## Real Pipeline Gate

The fastest measured H.264 profile was wired into the real pipeline as `video_preset=throughput`, then benchmarked against production output.

It was rejected:

- elapsed `104.088s`, speed `0.2882x`;
- SSIM `0.991078`, below the `0.995` gate.

The safe production preset remains `quality`:

- elapsed `104.490s`, speed `0.2871x`;
- SSIM `1.0`, PSNR `inf`;
- stage timing shows `58.186s` in clip/camera/background generation and `46.023s` in particles/logo overlay.

Audio first-run/cache-miss remains below target:

- `34.646s` audio generated in `41.101s`;
- speed `0.8429x`;
- cache `0/4`.
