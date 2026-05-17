# Portable Windows Release

## Goal

Create a stable Windows zip that users can extract and run without manually
installing Python or Node.

## Build

```powershell
powershell -ExecutionPolicy Bypass -File scripts/portable/build_portable_release.ps1 -Version v0.1.6
```

Output:

```text
dist/ambrouse-studio-v0.1.6-win64.zip
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
- production story renderer binary at
  `spam_audio_video/renderers/story_gpu_renderer/target/release/story_gpu_renderer.exe`.
- launcher scripts.
- GPU-safe `.env` defaults.

## Still Machine-Specific

- NVIDIA driver for CUDA/NVENC.
- Chrome/Chromium installation.
- first-time Gemini/GPT login in the browser profiles.
- model downloads/cache unless a full offline bundle is built separately.

## Story Renderer

`v0.1.6` packages the Rust/D3D11/NVENC renderer binary so the video pipeline can
use the production full-timeline path on fresh machines without installing
Rust. The renderer is required for 16:9 `60fps` H.264/NVENC outputs; the main
pipeline no longer falls back to the old segmented FFmpeg render path.

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
