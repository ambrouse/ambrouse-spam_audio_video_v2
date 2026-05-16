# 2026-05-16 Fast 4K60 Render Pipeline

## Summary
- Implemented period-only TTS input policy: commas are removed, natural chunk flushing only uses periods, and backend clamps `min_words` to at least 30.
- Updated frontend defaults: TTS IO workers `6`, rewrite workers `9`, chunk min `30`, seconds per image `30`.
- Split Browser Bridge port routing:
  - Rewrite + Gemini prompt generation use Gemini-selected ports.
  - GPT image generation uses GPT-selected ports.
  - Pipeline warms/pings selected ports before provider phases.
- Added GPT image text-only response detection in `toll-brouser-gpt-gemini`.
- Added render benchmark harness: `spam_audio_video/tools/benchmark_4k60_render.py`.
- Updated ffmpeg resolver to use the bundled `spam_audio_video/.venv` ffmpeg when system ffmpeg is absent.
- Removed the redundant single-clip re-encode pass before visual overlays.

## Validation
- `python -m unittest spam_audio_video.tests.test_tts_chunk_policy` passed.
- Targeted `py_compile` passed for edited backend/video/bridge files.
- `node --check spam_audio_video/source_full/frontend/app.js` passed.
- Real chunk output on `test-1/session_ch0001_to_ch0010`:
  - 201 `tts_inputs` files.
  - 0 comma violations.
  - 0 non-period endings.
  - 1 below-min final tail chunk because source text ended at 24 words.
- Real 4K60 render benchmark after single-clip optimization:
  - Output: `benchmark_4k60_smoke4.mp4`.
  - Duration: 30.0s.
  - Resolution: 3840x2160.
  - FPS: 60.
  - Encoder: `h264_nvenc`.
  - `gpu_fallback_used`: false.
  - Elapsed: 102.707s.
  - Speed: 0.2921x.
  - Previous same benchmark before optimization: 129.244s / 0.2321x.
  - Improvement: about 1.26x on one 30s 4K60 scene.
  - Report: `spam_audio_video/projects_workspace/projects/test-1/sessions/session_ch0001_to_ch0010/video/renders/benchmark_4k60_smoke4.benchmark.json`.

## Notes
- Bridge pytest was not runnable in the current environment because `pytest_httpserver` is missing.
- Full repository `compileall` timed out on the large tree, so validation used targeted compile checks plus focused tests.
