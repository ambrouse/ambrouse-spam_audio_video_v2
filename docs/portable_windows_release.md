# Portable Windows Release

## Goal

Create a stable Windows zip that users can extract and run without manually
installing Python or Node.

## Build

```powershell
powershell -ExecutionPolicy Bypass -File scripts/portable/build_portable_release.ps1 -Version v0.1.2
```

Output:

```text
dist/ambrouse-studio-v0.1.2-win64.zip
```

## Runtime Entry Points

Inside the extracted app:

```text
RUN.bat
CHECK_GPU.bat
REPAIR_TTS_CUDA.bat
```

`RUN.bat` prepares local virtual environments inside the extracted folder,
starts the browser bridge, then starts Story Pipeline Studio.

## Included

- source code for `spam_audio_video`.
- source code for `toll-brouser-gpt-gemini`.
- portable Python runtime.
- portable Node runtime.
- launcher scripts.
- GPU-safe `.env` defaults.

## Still Machine-Specific

- NVIDIA driver for CUDA/NVENC.
- Chrome/Chromium installation.
- first-time Gemini/GPT login in the browser profiles.
- model downloads/cache unless a full offline bundle is built separately.

## Bridge Port Scheduling

The browser bridge uses one shared `PortScheduler` for Gemini and GPT:

- each port handles one task at a time.
- waiting prompts stay in a queue.
- when a port finishes, the next queued task gets a ready port.
- rate-limited ports enter cooldown.
- if all ports are busy or cooling down, queued tasks wait until a port is ready.

`spam_audio_video` now sends GPT image prompts as a batch, so image generation
uses this scheduler instead of generating one scene at a time.

Video prompt generation also sends concurrent bridge requests using the same
scheduler behavior.

## Render Workers

Video render now defaults to `VIDEO_RENDER_WORKERS=6`.

The UI exposes `Render workers` in the GPT Image + Video Config panel.
Use this to raise/lower parallel FFmpeg clip rendering:

- `1`: safest, slowest.
- `6`: aggressive default for RTX 3060-class GPUs.
- `7-8`: try only if VRAM/driver remains stable.
