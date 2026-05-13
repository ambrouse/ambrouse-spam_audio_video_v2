# 2026-05-14 GPU runtime hardening log

## Completed

- Made audio runtime default to CUDA through `AudioPipelineService`.
- Added fail-fast CUDA validation in the VieNeu worker so CPU-only PyTorch cannot silently run production audio.
- Updated setup to treat GPU machines as CUDA targets by default and reinstall CUDA PyTorch when validation fails.
- Blocked CPU video encoding in the production path; `auto` now requires a verified hardware H.264 encoder.
- Fixed the FFmpeg hardware encoder probe size so NVENC is detected correctly.
- Changed TTS text cleanup/chunk/export punctuation policy to keep only `.` and `,`.
- Simplified GPU Setting UI output to a short runtime conclusion.
- Removed GPT port opening from the GPT/video config panel; Bridge tab owns port open/ping.
- Added `spam_audio_video/.env.example` and `.env` loading for setup/web runtime.

## Runtime Check

```text
GPU: NVIDIA GeForce RTX 3060, driver 595.71, 12288 MB
TTS torch: 2.11.0+cu128
TTS CUDA available: true, CUDA 12.8
Video auto encoder: h264_nvenc
```

## Current Conclusion

- Audio will run on GPU CUDA on this machine.
- Video will run through GPU NVENC on this machine.
- A fresh clone does not need `.env` to choose GPU; setup auto-detects `nvidia-smi` and runtime defaults to CUDA. `.env` is for explicit local overrides.

## Verification

- `python -m py_compile` passed for edited backend/runtime Python files.
- `node --check spam_audio_video/source_full/frontend/app.js` passed.
- `bash -n spam_audio_video/setup.sh` passed.
- Video encoder probe selected `h264_nvenc`.
