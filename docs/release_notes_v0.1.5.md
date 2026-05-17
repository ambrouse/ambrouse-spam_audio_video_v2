# Release Notes - v0.1.5

Superseded by `v0.1.6`, which removed the multi-clip combine/fallback path and
ships only the production Rust/D3D11/NVENC story timeline renderer.

## Highlights

- Fixed native 4K60 audio visualizer renders near the end of a timeline when a
  clip starts beyond the current WAV length.
- Video render now prefers the live `combined.wav` duration over stale analysis
  metadata, preventing extra native clips after audio was regenerated.
- Added visible progress for the post-native clip combine step so the web UI no
  longer appears idle after the last clip.

## Validation

Local validation on 2026-05-17:

| Check | Result |
| --- | --- |
| Python compile for video pipeline | Pass |
| Python unit tests | Pass, 3 tests |
| Rust `cargo fmt`, release tests, and release build | Pass |
| Native failing clip replay | Pass: `clip_0032.mp4` rendered in `28.943s` |
| Full 4K60 pipeline resume with cached native clips | Pass: 32 clips, final silent MP4 and audio MP4 produced |
| Output media probe | Pass: 3840x2160, 60fps, H.264 video, AAC stereo audio, `00:30:58.18` |

## Runtime Notes

- Native Rust/D3D11/NVENC still renders the production clips and shader visual
  overlays.
- FFmpeg is still used after native rendering for multi-clip `xfade` combine
  and final audio mux. This is expected in `v0.1.5`.
- The verified full 4K60 resume run used cached native clips; the remaining
  heavy stages were `combine_clips_s=1884.695` and `mux_audio_s=203.25`.

## Fixed Bug

The web render appeared to stop after native clips because the cached
`analysis_manifest.json` reported `1936.191s`, while the current
`combined.wav` was `1858.183s`. That made the renderer plan an extra late
clip. The native visualizer then attempted to slice past the end of the WAV.

`v0.1.5` fixes both sides: the pipeline recalculates audio duration from the
current WAV during render, and the native visualizer returns silent bars when a
frame is outside audio bounds.
