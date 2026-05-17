# Setup Release Validation Log - 2026-05-17

## Scope

- Hardened `spam_audio_video/setup.sh` for clone/release bring-up.
- Added CLI flags for install-only, assumed yes, production validation, and TTS device selection.
- Added real VoxCPM one-chunk validation with cache disabled and quality envelope checks.
- Normalized shell setup scripts to LF.
- Added CI for setup syntax, production module compile, and TTS chunk policy unit tests.

## Commands Run

```bash
bash -n spam_audio_video/setup.sh
bash -n toll-brouser-gpt-gemini/setup.sh
bash -n toll-brouser-gpt-gemini/bin/setup.sh
python -m unittest discover -s spam_audio_video/tests
python -m py_compile spam_audio_video/tools/benchmark_tts_pipeline.py spam_audio_video/source_full/backend/pipeline_service.py spam_audio_video/auto_text_to_voice/vieneu_worker.py spam_audio_video/auto_generate_video/pipeline.py
cd spam_audio_video
bash setup.sh --install-only --yes --production-validate --tts-device cuda
bash setup.sh --install-only --yes --skip-production-validation --tts-device cuda
D:/appSetting/codeApp/gitBase/Git/bin/bash.exe setup.sh --install-only --yes --production-validate --tts-device cuda
D:/appSetting/codeApp/gitBase/Git/bin/bash.exe setup.sh --setup-only --yes
D:/appSetting/codeApp/gitBase/Git/bin/bash.exe -lc 'uv run pytest tests/ci/test_gemini_bridge_batch.py -q'
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/portable/build_portable_release.ps1 -Version v0.1.3
Expand-Archive dist/ambrouse-studio-v0.1.3-win64.zip D:\ambrouse-release-test-v013
D:/appSetting/codeApp/gitBase/Git/bin/bash.exe setup.sh --install-only --yes --production-validate --tts-device cuda
cmd /c CHECK_GPU.bat
```

## Results

| Check | Result |
| --- | --- |
| Setup syntax | Pass |
| Bridge setup syntax | Pass after LF normalization |
| Unit tests | Pass, 2 tests |
| Production setup validation | Pass |
| Install-only no-server behavior | Pass |
| Real VoxCPM WAV | Pass |
| Real VoxCPM WAV envelope | Pass: peak `-6.06 dBFS`, RMS `-18.78 dBFS` |
| Bridge setup-only via Git Bash | Pass |
| Gemini/GPT bridge batch tests | Pass, 9 tests |
| Portable `v0.1.3` zip build | Pass |
| Extracted release setup validation | Pass: peak `-6.13 dBFS`, RMS `-18.43 dBFS` |
| Extracted release GPU check | Pass: CUDA torch available, encoder `h264_nvenc` |

Generated setup-validation reports are now ignored and were removed from
source during the `v0.1.6` cleanup. Regenerate them locally with
`bash setup.sh --install-only --yes --production-validate --tts-device cuda`
when validating a fresh machine.

## Notes

- `gh` CLI is not installed and no `GITHUB_TOKEN`/`GH_TOKEN` is present in the shell, so GitHub Releases cannot be created through `gh` from this machine unless credentials/tooling are added.
- Rust/Cargo is not installed on this machine, so the native renderer cannot be compiled locally until Rust is installed.
- PowerShell resolves plain `bash` to WSL on this machine; Windows release validation used Git Bash explicitly to match the intended user setup path.
- The portable zip is intentionally ignored by Git and should be uploaded as a GitHub Release asset, not committed.
- Existing unrelated working-tree changes were preserved.
