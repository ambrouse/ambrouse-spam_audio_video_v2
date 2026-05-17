# 2026-05-17 Production Story Timeline Main Path

## Scope

- Replace the production video main path with one Rust/D3D11/NVENC full-timeline render.
- Remove the old segmented clip render/combine path from the normal web render output.
- Keep the audio pipeline unchanged and mux the existing combined WAV after video.

## Code Changes

- `VideoPipeline.render_video(...)` now takes the production full-timeline branch when the output is 16:9 `60fps` `h264_nvenc`.
- `build_story_renderer_input(...)` now passes the full image sequence, timeline duration, transition duration, audio visualizer color, and benchmark override safely.
- The Rust renderer now loads each unique scene image once, keeps a scene sequence, renders current/next scenes with shader dissolve, then encodes one continuous H.264 stream.
- Shared audio mux logic moved into `_attach_audio_to_render(...)`.

## Main-Pipeline Cleanup

- `VideoPipeline.render_video(...)` now has one production video path only:
  Rust/D3D11/NVENC full timeline, then optional audio mux.
- The old segmented clip renderer, clip combine path, static-layer cache helpers,
  FFmpeg visual overlay helper, and clip cache validation helpers were removed
  from the main pipeline code.
- The Rust renderer CLI now exposes only `render`; old probe/encode-ceiling
  commands were removed.
- Production artifacts now use `*.render_input.json` and `*.render_report.json`
  when retained for debugging, not `*.native_*`.
- Validation after cleanup: 3-minute 1080p60 with-audio render completed in
  `22.623s` total, `16.838s` timeline render, `5.386s` audio mux, `7.9566x`
  realtime.

## Validation

| Check | Result |
| --- | --- |
| `python -m py_compile spam_audio_video/auto_generate_video/pipeline.py` | Pass |
| `python -m unittest discover -s spam_audio_video/tests -p "test_*.py"` | Pass, 3 tests |
| `cargo fmt --check` | Pass |
| `cargo test --release` | Pass |
| `cargo build --release` | Pass |
| 3-minute 4K60 with-audio pipeline benchmark | Pass, `94.291s` total video stage |

## 3-Minute Output

- Final review file was produced during validation:
  `story_render_3m_eval_with_audio.mp4`
- Story render time: `87.908s`.
- Audio mux time: `5.593s`.
- Renderer process peak working set from sampling: about `421 MB`.
- GPU memory sampling was whole-device, so it includes other running processes.

## Fast 1080p Follow-Up

- Web/backend defaults moved to `1920x1080 @ 60fps` with `VIDEO_PRESET=throughput`.
- Story renderer throughput maps to NVENC `p1`.
- Story renderer bitrate now scales by resolution; 1080p uses an `8 Mbps` floor.
- Story renderer image prep uses faster resize filters and adaptive blur.
- VoxCPM default inference steps moved from `8` to `6` through
  `SPAM_TTS_INFERENCE_TIMESTEPS`.
- 3-minute 1080p60 with-audio validation:
  - total video stage: `23.305s`;
  - story timeline: `17.194s`;
  - audio mux: `5.613s`;
  - speed: `7.7174x realtime`;
  - renderer peak working set: about `132 MB`.

## Visual Polish Follow-Up

- Audio visualizer is now drawn as two side clusters of circular dot stacks
  instead of rectangular bars.
- Story renderer particles use a soft circle texture and move vertically only.
- 3-minute 1080p60 visual validation completed in `22.701s` total video stage
  with `16.838s` story timeline render.

## Audio Aggressive Follow-Up

- VoxCPM generation now runs under `torch.inference_mode()`.
- CUDA runtime enables TF32 matmul/cuDNN benchmark where available.
- Default TTS profile is now the most aggressive stable profile found:
  - `SPAM_TTS_INFERENCE_TIMESTEPS=6`;
  - `SPAM_TTS_RETRY_BADCASE=1`;
  - `SPAM_TTS_RETRY_BADCASE_MAX_TIMES=1`;
  - `SPAM_TTS_CFG_VALUE=2.0`;
  - `SPAM_TTS_MAX_LEN_SCALE=2.9`;
  - `SPAM_TTS_MAX_LEN_PADDING=70`.
- Full retry disable was tested and rejected because VoxCPM can crash internally
  with `latent_pred` unassigned.
- Audio merge now streams WAV blocks directly to `combined.wav` instead of
  concatenating the entire session in RAM.
- Current full audio validation:
  - generated files: `201`;
  - combined WAV duration: `1855.577s`;
  - previous audio run: `1114.424s`;
  - aggressive stable run: `1102.582s`;
  - speed-up: about `1.06%`.
- 3-minute 1080p60 integrated video+audio sample passed FFmpeg decode:
  `180.00s`, `1920x1080`, `60fps`, AAC stereo.
