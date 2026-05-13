# Windows Portable Release

This folder contains the release builder and launcher scripts for the Windows
portable app.

Goal:

- user does not need to install Python manually.
- user does not need to install Node manually.
- release zip contains portable Python and Node runtimes.
- first run creates local virtual environments inside the extracted folder.
- GPU audio/video defaults stay enabled.

Still required on the target machine:

- Windows 10/11 x64.
- NVIDIA driver when using CUDA/NVENC.
- Chrome or Chromium for Gemini/GPT browser sessions.
- first-time login to Gemini/GPT in the opened browser profiles.
- internet on first run unless the release was built with wheelhouse/model cache.

Build:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/portable/build_portable_release.ps1 -Version v0.1.1
```

Output:

```text
dist/ambrouse-studio-v0.1.1-win64.zip
```

User run:

```text
RUN.bat
```
