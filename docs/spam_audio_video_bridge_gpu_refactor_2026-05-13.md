# spam_audio_video bridge/GPU refactor - 2026-05-13

## Scope
- Rewrite, video prompt, and image generation now call `toll-brouser-gpt-gemini` through the local bridge at `http://127.0.0.1:8008`.
- Legacy Gemini API endpoint/default `20128` and direct GPT Playwright image generation were removed from the active production path.
- UI now has Bridge and GPU Setting tabs for opening/pinging ports, testing Gemini chat, testing GPT images, and checking GPU/audio/video runtime status.
- Audio text cleanup and chunking now target TTS-friendly chunks: default 16-64 words, preserve `.` `,` `;`, convert question/exclamation/colon style pauses instead of dropping meaning.
- Video render auto-selects a verified FFmpeg hardware encoder first and only falls back to CPU `libx264` when the encoder probe fails.

## Important Behavior
- Sending old provider names such as `openai_compat`, `gemini_web`, `gpt_web`, or `gpt` is treated as compatibility input and mapped to bridge providers.
- Rewrite validates that long Vietnamese output has diacritics and rejects markdown/code fences/UI chrome text.
- `GET /api/gpu/status` reports torch/CUDA, `nvidia-smi`, FFmpeg encoders, selected video encoder, and audio worker status.
- TTS worker stderr is now written to `spam_audio_video/projects_workspace/runtime/tts_worker_stderr.log` and surfaced in runtime errors.

## Runtime Notes
- Tested bridge ports: 9222, 9223, 9224.
- Current local backend URL: `http://127.0.0.1:8123`.
- Current bridge URL: `http://127.0.0.1:8008`.
- On this laptop, torch is not installed in the backend Python, so audio synthesis cannot be completed here. The UI/API now reports the exact missing dependency instead of failing silently.

## Setup Update
- `spam_audio_video/setup.sh` now inventories OS, Python candidates, PyTorch/CUDA, and `nvidia-smi` into the setup log.
- Web Python and TTS Python are selected separately: web accepts Python 3.10+, while Windows TTS requires Python 3.12.
- If Python 3.12, Node/npm, 9router, web deps, or VieNeu/TTS deps are missing, setup asks `y/n` before installing or repairing them.
- Existing web/TTS venvs are reused when validation passes, avoiding unnecessary reinstalls.

## Verified End-to-End Output
- Real E2E test project: `e2e-real-20260513/session_ch0001_to_ch0001`.
- Rewrite, clean, chunk, audio synthesis, prompt generation, GPT image generation, and video render all passed through HTTP requests.
- Audio output: `audio/combined.wav`, 26.549s, 44100 Hz, mono.
- Video output: `video/story_with_audio.mp4`, 26.55s, 1280x720, 30 fps, AAC 48k stereo.
- This machine has no CUDA/NVIDIA GPU, so audio used CPU fallback. Video encoder used `h264_qsv`.
