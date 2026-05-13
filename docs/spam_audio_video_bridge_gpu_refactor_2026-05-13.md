# spam_audio_video bridge/GPU refactor - 2026-05-13

## Scope
- Rewrite, video prompt, and image generation now call `toll-brouser-gpt-gemini` through the local bridge at `http://127.0.0.1:8008`.
- Legacy Gemini API endpoint/default `20128` and direct GPT Playwright image generation were removed from the active production path.
- UI now has Bridge and GPU Setting tabs for opening/pinging ports, testing Gemini chat, testing GPT images, and checking GPU/audio/video runtime status.
- Audio text cleanup and chunking now target TTS-friendly chunks: default 16-64 words and only preserve `.` and `,`; other punctuation is deleted instead of converted.
- Video render auto-selects a verified FFmpeg hardware encoder and blocks CPU `libx264` in the production path.

## Important Behavior
- Sending old provider names such as `openai_compat`, `gemini_web`, `gpt_web`, or `gpt` is treated as compatibility input and mapped to bridge providers.
- Rewrite validates that long Vietnamese output has diacritics and rejects markdown/code fences/UI chrome text.
- `GET /api/gpu/status` reports torch/CUDA, `nvidia-smi`, FFmpeg encoders, selected video encoder, and audio worker status.
- TTS worker stderr is now written to `spam_audio_video/projects_workspace/runtime/tts_worker_stderr.log` and surfaced in runtime errors.

## Runtime Notes
- Tested bridge ports: 9222, 9223, 9224.
- Current local backend URL: `http://127.0.0.1:8080` unless setup auto-selects another free port.
- Current bridge URL: `http://127.0.0.1:8008`.
- GPU status is based on the TTS worker venv, not just the web backend venv. A CPU-only TTS torch install now fails fast instead of running audio on CPU.
- Fresh clones do not need `.env` to choose GPU: setup uses CUDA when `nvidia-smi` exists and runtime defaults audio to CUDA.

## Setup Update
- `spam_audio_video/setup.sh` now inventories OS, Python candidates, PyTorch/CUDA, and `nvidia-smi` into the setup log.
- Web Python and TTS Python are selected separately: web accepts Python 3.10+, while Windows TTS requires Python 3.12.
- If Python 3.12, Node/npm, 9router, web deps, or VieNeu/TTS deps are missing, setup asks `y/n` before installing or repairing them.
- Existing web/TTS venvs are reused when validation passes, avoiding unnecessary reinstalls.
- `spam_audio_video/.env.example` documents optional local overrides; GPU-safe defaults live in code/setup.

## Verified End-to-End Output
- Real E2E test project: `e2e-real-20260513/session_ch0001_to_ch0001`.
- Rewrite, clean, chunk, audio synthesis, prompt generation, GPT image generation, and video render all passed through HTTP requests.
- Audio output: `audio/combined.wav`, 26.549s, 44100 Hz, mono.
- Video output: `video/story_with_audio.mp4`, 26.55s, 1280x720, 30 fps, AAC 48k stereo.
- Follow-up on 2026-05-14: current target machine has an RTX 3060. Video selects `h264_nvenc`; TTS venv now reports `torch=2.11.0+cu128`, `cuda_available=true`, so audio and video both use GPU paths.
