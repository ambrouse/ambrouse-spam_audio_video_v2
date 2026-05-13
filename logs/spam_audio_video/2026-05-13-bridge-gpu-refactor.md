# 2026-05-13 spam_audio_video bridge/GPU refactor log

## Completed
- Added bridge client and backend endpoints for bridge status/open/chat-test/image-test.
- Routed rewrite and video prompt generation through Gemini bridge.
- Routed image generation through GPT bridge and removed the direct GPT Playwright image generation implementation from the active video pipeline.
- Added GPU status/prewarm/check endpoints and GPU Setting UI.
- Updated chunk defaults to 16-64 words and verified pause-aware chunk output.
- Fixed default prompt encoding for rewrite/video prompt in backend, frontend, and workspace prompt defaults.
- Added stderr logging for the TTS worker.

## Real Request Tests
- `POST /api/bridge/open` with ports 9222, 9223, 9224: success.
- `POST /api/bridge/chat-test`: Gemini returned `OK`, used port 9222.
- `POST /api/bridge/image-test`: GPT returned PNG, 2,023,712 bytes, source size 1672x941.
- Rewrite test intentionally sent `provider=openai_compat`; backend mapped to `bridge_gemini`, summary success 1/1.
- Audio clean + chunk test produced 6 TTS text files, each 16-25 words, no below/above limit chunks.
- Video prompt pipeline produced a one-line English image prompt via Gemini bridge.
- Video image pipeline produced `scene_0001.png`, PNG 1672x941, ratio 1.7768, 2,566,839 bytes.
- Video render produced `story_with_audio.mp4`, duration 00:00:03.00, 1280x720 DAR 16:9, 30 fps, AAC 48k stereo.
- UI Playwright check on desktop/mobile Bridge/GPU tabs: no console errors or page errors; screenshots saved under `spam_audio_video/projects_workspace/runtime/ui_checks`.

## Remaining Runtime Blocker
- `GET /api/pipeline/audio/models` reports TTS worker not ready because backend Python lacks runtime dependencies:
  `ModuleNotFoundError: No module named 'numpy'`.
- GPU audio synthesis still needs a proper VieNeu/VoxCPM runtime install on the target machine before real TTS generation can be verified.

## Follow-up Setup Fix
- Updated `spam_audio_video/setup.sh` to separate web Python from TTS Python.
- Added runtime inventory logging for OS, Python executable/version, PyTorch/CUDA, and `nvidia-smi`.
- Added `y/n` prompts before installing Python 3.12 via winget, Node/npm via winget, 9router via npm, web dependencies, and VieNeu/TTS dependencies.
- Added validation/reuse for existing `.venv` and VieNeu `.venv-win`; invalid or Python-3.11 TTS venvs are recreated only after confirmation.

## Full Real E2E Retest
- Ran `SETUP_ASSUME_YES=1 SETUP_INSTALL_ONLY=1 SETUP_TTS_DEVICE=auto bash setup.sh`; setup completed including TTS prewarm.
- Runtime after setup:
  - Web Python: `spam_audio_video/.venv/Scripts/python.exe`.
  - TTS Python: `spam_audio_video/auto_text_to_voice/VieNeu-TTS/.venv-win/Scripts/python.exe`.
  - TTS torch: `2.11.0+cpu`, CUDA unavailable on this machine.
- Test project: `e2e-real-20260513`, session `session_ch0001_to_ch0001`.
- Rewrite:
  - `POST /api/convert/projects/e2e-real-20260513/rewrite`.
  - Provider `bridge_gemini`, success 1/1.
  - Output verified: Vietnamese Unicode present, no markdown, no prompt echo.
- Audio clean/chunk:
  - Clean success 1/1.
  - Chunk success: 4 TTS inputs, word counts 44, 27, 22, 24; all within 16-64 and end with `.`.
- Audio synthesis:
  - `POST /api/pipeline/audio/run`, voice `su-review`, model `voxcpm_vn`.
  - Success true, generated 4 chunk WAV files plus `combined.wav`.
  - `combined.wav`: 2,341,704 bytes, 26.549s, 44100 Hz, mono.
  - Runtime device: CPU, valid fallback because `nvidia-smi` and CUDA are unavailable on this laptop.
- Video:
  - Prompt via Gemini bridge: success, 1 scene, prompt 97 words.
  - Image via GPT bridge: success, PNG 2,412,460 bytes, 1672x941, ratio 1.7768.
  - Render: success, `story_with_audio.mp4`, 26.55s, 1280x720, DAR 16:9, 30 fps, AAC 48k stereo.
  - Video encoder selected: `h264_qsv`, no CPU `libx264` fallback.
- Final API/UI:
  - `/api/gpu/status` success; now reports TTS Python 3.12.10 and TTS torch status.
  - `/api/pipeline/audio/models` success.
  - `/api/bridge/status` success, ports 9222/9223/9224 active.
  - Playwright desktop/mobile Bridge/GPU UI check: no console or page errors.
