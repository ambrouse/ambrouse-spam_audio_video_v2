# Release Notes - v0.1.3

## Highlights

- Hardened `spam_audio_video/setup.sh` for fresh clone and release installs.
- Added install-only and production-validation modes:

```bash
cd spam_audio_video
bash setup.sh --install-only --yes --production-validate --tts-device cuda
```

- Added a real VoxCPM validation gate that generates a WAV with cache disabled,
  `temperature=0.05`, and `postprocess=false`.
- Added WAV envelope checks to reject clipped or overly hot validation audio.
- Added CI coverage for shell syntax, production Python compile, and TTS chunk
  policy unit tests.
- Kept benchmark media ignored while allowing report files to be committed.

## Validation

Local validation passed on 2026-05-17:

| Check | Result |
| --- | --- |
| `bash -n` setup scripts | Pass |
| Python module compile | Pass |
| Unit tests | Pass |
| Setup install-only production validation | Pass |
| Real VoxCPM WAV generated | Pass |
| Portable zip build | Pass |
| Extracted release setup production validation | Pass |
| Extracted release bridge batch tests | Pass, 9 tests |
| Extracted release GPU check | Pass, CUDA torch + `h264_nvenc` |

The generated benchmark report was removed from source during the `v0.1.6`
cleanup. Regenerate it locally with setup production validation when preparing
a release:

```bash
cd spam_audio_video
bash setup.sh --install-only --yes --production-validate --tts-device cuda
```

Observed validation WAV: 3.924s, peak -6.06 dBFS, RMS -18.78 dBFS,
cache disabled.

Extracted release validation generated a separate real WAV in the extracted
folder: 3.548s, peak -6.13 dBFS, RMS -18.43 dBFS, cache disabled.

## Known Limits

- GitHub-hosted CI does not run the real VoxCPM GPU validation; run the local
  setup validation command before publishing a release.
- A GitHub Release requires either GitHub CLI authentication or a valid
  `GITHUB_TOKEN`/`GH_TOKEN` in the publishing shell.
