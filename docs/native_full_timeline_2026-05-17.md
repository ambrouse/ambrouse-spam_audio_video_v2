# Production Story Timeline Renderer - 2026-05-17

## Decision

The main video path now renders the whole story timeline in one optimized pass:

- Rust story renderer;
- D3D11 image textures and shader-side crop/motion/overlay/audio bars;
- direct NVENC H.264 encode;
- FFmpeg only for MP4 remux and final audio mux.

The old segmented clip render/combine path has been removed from the main
pipeline. Production video now fails fast when the optimized renderer contract
is not available instead of silently falling back to the old path.

## Runtime Contract

- Supported main path: 16:9, 60fps, `h264_nvenc`.
- Optional binary override: `SPAM_VIDEO_RENDERER_BIN`.
- There is no segmented render fallback in the main pipeline.
- Audio pipeline is unchanged; video mux reads the existing combined WAV.

## 3-Minute Validation

Test command used the real `VideoPipeline.render_video(...)` path through the
4K60 benchmark helper with audio enabled.

Result:

| Metric | Value |
| --- | ---: |
| Output duration | `180.00s` |
| Resolution / FPS | `3840x2160 @ 60fps` |
| Story timeline render | `87.908s` |
| Final audio mux | `5.593s` |
| Total video stage | `94.291s` |
| Story scene prep | `15.666s` |
| Story render+encode | `71.232s` |
| Renderer peak working set | about `421 MB` |
| Output with audio | `story_render_3m_eval_with_audio.mp4` |

GPU memory numbers from Windows sampling are whole-device readings and include
other already-running processes, so use them as an environment snapshot rather
than renderer-only memory.

## Long-Run Stability Notes

- The renderer no longer accumulates per-clip FFmpeg processes, clip manifests,
  or xfade concat graphs during the main path.
- Unique image textures are deduplicated once per full render, then reused by
  the timeline sequence.
- Python returns after one story renderer process plus one mux process, reducing RAM/VRAM
  churn for 20-40 hour jobs.

## Fast HD Profile

Later on 2026-05-17 the default production profile was moved to `1080p60` with
story renderer NVENC throughput preset for faster web runs.

Changes:

- UI/backend defaults: `1920x1080 @ 60fps`.
- `VIDEO_PRESET=throughput` by default.
- Story renderer NVENC maps throughput to preset `p1`.
- Story renderer bitrate scales by output resolution, with `1080p` floor at `8 Mbps`.
- Story renderer image prep uses faster resize filters and adaptive blur.
- VoxCPM default `SPAM_TTS_INFERENCE_TIMESTEPS=6`; raise back to `8` after
  listening tests if a voice needs extra stability.

3-minute validation:

| Metric | Value |
| --- | ---: |
| Output duration | `180.00s` |
| Resolution / FPS | `1920x1080 @ 60fps` |
| Story timeline render | `17.194s` |
| Final audio mux | `5.613s` |
| Total video stage | `23.305s` |
| Render speed | `7.7174x realtime` |
| Story scene prep | `3.864s` |
| Story render+encode | `12.767s` |
| Renderer peak working set | about `132 MB` |
| Output with audio | `story_render_1080p60_eval_with_audio.mp4` |

Visual follow-up:

- Audio visualizer changed from rectangular bars to two side clusters of round
  dot stacks.
- Dust/spark overlays now use a soft circle texture.
- Particle motion is vertical only: top-to-bottom dust and bottom-to-top sparks,
  without horizontal sway.
- 3-minute 1080p60 visual validation completed in `22.701s` total video stage
  with `16.838s` story timeline render.

## Audio Aggressive Profile Follow-Up

The TTS path now defaults to the most aggressive stable VoxCPM profile found in
testing:

- `SPAM_TTS_INFERENCE_TIMESTEPS=6`;
- `SPAM_TTS_RETRY_BADCASE=1`;
- `SPAM_TTS_RETRY_BADCASE_MAX_TIMES=1`;
- `SPAM_TTS_CFG_VALUE=2.0`;
- `SPAM_TTS_MAX_LEN_SCALE=2.9`;
- `SPAM_TTS_MAX_LEN_PADDING=70`.

Fully disabling VoxCPM `retry_badcase` was tested and rejected because the
upstream model can crash internally with an unassigned `latent_pred` value.

The worker also now wraps generation in `torch.inference_mode()`, enables CUDA
TF32/cuDNN benchmark where available, and writes `combined.wav` with a streaming
merge instead of concatenating the whole audio timeline in RAM.

Validation on the current `test-1/session_ch0001_to_ch0010` input:

| Metric | Value |
| --- | ---: |
| Generated files | `201` |
| Combined WAV duration | `1855.577s` |
| Previous full audio run | `1114.424s` |
| Aggressive stable audio run | `1102.582s` |
| Audio speed-up | about `1.06%` |
| 3-minute 1080p60 video+audio sample | `22.692s`, `7.9323x realtime` |

The speed gain is small because this voice/model is still dominated by VoxCPM
decoder inference. The larger stability gain is RAM behavior during long
audio merges: merge memory no longer scales with total story duration.
