# 2026-05-17 Native Clip End-Audio Hotfix

## Scope

- Investigate web render stopping after native 4K60 clip generation.
- Fix the end-of-audio crash and verify the main pipeline creates both silent
  and audio-attached outputs.
- Prepare `v0.1.5` hotfix release.

## Findings

- The failed native run stopped at `clip_0032`, leaving a zero-byte
  `clip_0032.native_candidate.h264` and no native report.
- `analysis_manifest.json` still reported `1936.191s`, but the current
  `combined.wav` was `1858.183s`.
- The late clip's `audio_start_seconds` reached the end of the WAV, and the
  Rust visualizer sliced audio with `start > end`.
- Audio generation was slow because the run had cache enabled but recorded
  `hits=0` and `misses=201`; it was a full fresh TTS generation, not a cache
  reuse path.

## Fix

- Native visualizer now emits zero bars for frames outside the loaded WAV.
- Render planning now refreshes audio duration from the current session WAV
  before building the image sequence.
- Video pipeline now reports `video_render_combine_clips` before and after the
  FFmpeg timeline combine stage.

## Validation

| Check | Result |
| --- | --- |
| `python -m py_compile spam_audio_video/auto_generate_video/pipeline.py` | Pass |
| `python -m unittest discover -s spam_audio_video/tests -p "test_*.py"` | Pass, 3 tests |
| `cargo fmt` | Pass |
| `cargo test --release` | Pass |
| `cargo build --release` | Pass |
| Direct native replay of failing `clip_0032.native_input.json` | Pass, `28.943s` |
| Main pipeline resume at 3840x2160 60fps with audio | Pass |

## Full Pipeline Resume Result

- `scene_count`: 32
- `audio_duration_seconds`: `1858.183`
- `native_gpu_renderer_used`: `true`
- `combine_clips_s`: `1884.695`
- `mux_audio_s`: `203.25`
- `total_render_video_s`: `2261.356`
- Silent output: `story_render_hotfix_check.mp4`
- Audio output: `story_render_hotfix_check_with_audio.mp4`
