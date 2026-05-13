# GPU Runtime Contract - 2026-05-14

## Current Decision

Fresh clone is GPU-first without requiring a `.env` file.

- `setup.sh` defaults `SETUP_TTS_DEVICE=auto`.
- If `nvidia-smi` exists, setup installs CUDA PyTorch for the VieNeu TTS venv.
- Runtime audio defaults to `SPAM_TTS_DEVICE=cuda`.
- A CPU-only TTS PyTorch install now fails fast instead of silently generating audio on CPU.
- Video render defaults `VIDEO_ENCODER=auto` and requires a working hardware H.264 encoder.
- CPU `libx264` is disabled in the production video path.

## Current Machine Check

Observed local machine:

```text
GPU: NVIDIA GeForce RTX 3060, driver 595.71, 12288 MB
TTS PyTorch: 2.11.0+cu128
TTS CUDA: true, CUDA 12.8
Video encoder auto: h264_nvenc
```

Conclusion:

```text
Audio real run: GPU CUDA.
Video real run: will run on GPU through h264_nvenc.
```

## Repair Command If CUDA Is Missing

Run this from `spam_audio_video/` to reinstall the TTS runtime for CUDA:

```powershell
$env:SETUP_TTS_DEVICE="cuda"
$env:SETUP_INSTALL_ONLY="1"
bash setup.sh
```

Restart the web backend after setup finishes so the worker uses the repaired venv.

## Optional `.env`

`.env` is optional. Use it only for explicit local overrides:

```text
SETUP_TTS_DEVICE=cuda
SPAM_TTS_DEVICE=cuda
PORT=8080
BRIDGE_BASE_URL=http://127.0.0.1:8008
BRIDGE_PORTS=9222,9223,9224
VIDEO_ENCODER=auto
```

The template is `spam_audio_video/.env.example`.

## UI Behavior

The GPU Setting tab reports simple conclusions:

- GPU detected or missing.
- TTS PyTorch installed or missing.
- TTS CUDA available or missing.
- Audio real-run decision.
- Video real-run encoder.

Raw JSON is intentionally hidden from the main status box to make runtime checks faster.

## Bridge Port Ownership

Opening ports belongs to the Bridge tab.

The GPT/video config tab only stores bridge ports used by image generation and status checks; it no longer opens GPT ports directly.
