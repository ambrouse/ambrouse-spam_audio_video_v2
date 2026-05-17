# 2026-05-17 Source Clean And v0.1.6 Release Prep

## Scope

- Cleaned production source after the Rust/D3D11/NVENC story renderer became
  the only video path.
- Removed tracked benchmark reports and old renderer tree from source.
- Kept the current VoxCPM-1.5-VN audio pipeline and removed the failed VoxCPM2
  experiment artifacts.
- Hardened release packaging for fresh Windows machines and long pipeline runs.

## Stability Fixes

- Added a source contract test so runtime code cannot reintroduce the old
  segmented clip renderer, native feature flag, or non-streaming audio merge.
- Kept audio merge streaming through `soundfile.SoundFile` blocks, avoiding
  whole-session `np.concatenate` growth during long 20-40 hour runs.
- Moved TTS worker Python resolution to prefer the short setup runtime
  `D:\.vieneu-<hash>` or `SPAM_TTS_PYTHON` before the compatibility junction.
  This fixed portable prewarm failure caused by Windows `MAX_PATH` when the
  extracted release path was long.
- Exported `SPAM_TTS_PYTHON` from setup after VieNeu runtime validation so the
  web backend and setup prewarm use the same known-good TTS Python.

## Cleanup

- Deleted generated setup-validation benchmark reports from source; future
  local reports stay under ignored benchmark folders.
- Deleted the old tracked `spam_audio_video/native_renderers/story_gpu_renderer`
  tree. The production renderer source now lives at
  `spam_audio_video/renderers/story_gpu_renderer`.
- Cleaned local video outputs for the `test-1/session_ch0001_to_ch0010`
  workspace while leaving audio artifacts in place.
- Removed old portable zips before rebuilding `v0.1.6`.

## Validation

| Check | Result |
| --- | --- |
| Production Python compile | Pass |
| `python -m unittest discover -s spam_audio_video/tests -p "test_*.py"` | Pass, 8 tests |
| Setup shell syntax | Pass |
| `cargo fmt --check` | Pass |
| `cargo build --release` | Pass |
| `cargo test --release` | Pass |
| Portable build | Pass: `dist/ambrouse-studio-v0.1.6-win64.zip` |
| Zip contract | Pass: renderer exe present, no old native/clip/VoxCPM2 artifacts |
| Extracted release setup | Pass: install-only, skip production validation, CUDA TTS prewarm |

## Notes

- Full real VoxCPM synthesis validation was not rerun during this cleanup
  because the user asked to keep audio artifacts and the current audio model.
- The portable setup validation did exercise dependency installation, CUDA TTS
  runtime validation, and TTS prewarm from the extracted zip.
