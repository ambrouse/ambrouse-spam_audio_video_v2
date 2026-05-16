# Video/Audio 8x4x Optimization - 2026-05-16

## Summary

This task starts the next optimization pass for the production audio/video pipeline.

Hard targets:

- video render: `>8x` faster than the locked 4K60 FFmpeg baseline;
- audio/TTS: `>4x` faster than the locked real TTS baseline on first-run/cache-miss synthesis;
- no quality, voice, style, timing, or effect removal.

## Audio Checkpoint

The first implemented optimization is a content-addressed TTS WAV cache.

Cache key includes:

- input text;
- voice profile;
- reference audio hash;
- reference text;
- model key;
- device/mode;
- inference, trim, and postprocess settings.

When all chunks hit cache, the worker no longer loads VoxCPM. It copies cached WAV files, rebuilds the combined WAV with the existing pause policy, and writes normal manifests.

Smoke result:

- 3 chunk no-cache run: `31.814s`.
- 3 chunk prompt-cache fresh run: `30.390s`.
- 3 chunk v2 cache-hit lazy-load run: `1.702s`.
- Effective rerun multiplier: `18.6969x`.

This is a quality-preserving rerun acceleration because the output chunks are reused exactly from cache. It does not yet solve first-time TTS generation speed.

The worker also reuses VoxCPM prompt/reference cache for generated chunks. That reduced the 3-chunk fresh-run smoke only slightly, so first-time synthesis remains model-inference bound.

Per the updated requirement, cache-hit/rerun acceleration does not count as passing the main audio target. It stays as a supporting optimization only.

## Fresh-Run TTS Direction

The installed VoxCPM package does not expose a true public batch generation API. Its CLI `batch` command also loops text items sequentially.

The internal model `_inference(...)` accepts batch-shaped tensors, so a private batched inference prototype is the next viable path. It must solve per-sample stop handling and variable output lengths without changing model settings or voice style.

Current first-run probes did not pass:

- 2 parallel TTS workers were slower than one worker on RTX 3060.
- Private true batch B=4 ran, but output durations matched across samples because stop handling is not per sample, so quality parity failed.
- Merging chunks was not materially faster and changes pacing risk.
- `triton-windows` enabled compile experiments, but first-run compile overhead was too high. The production worker now keeps compile off unless `SPAM_TTS_TORCH_COMPILE=1` is set.

## Benchmarking

New tool:

```powershell
python spam_audio_video/tools/benchmark_tts_pipeline.py --project-id test-1 --session-id session_ch0001_to_ch0010 --text-limit 3 --scenario smoke_no_cache_3_chunks --no-cache
```

Artifacts are written under:

```text
spam_audio_video/benchmarks/audio_8x4x/
```

Each run stores input metadata, output WAVs, benchmark JSON, quality JSON, summary, worker logs, and `nvidia-smi` output when available.

## Remaining Work

- Lock full-session audio baseline and cache-hit benchmark.
- Investigate VoxCPM batch/reference-cache support for fresh-run speed.
- Continue the native video renderer path; the current FFmpeg filter/pipe path and previous native speed probe have not passed the video `>8x` quality gate.
- The machine has `nvEncodeAPI64.dll`, and an `nvEncodeAPI.h` header is available from the local Unreal Engine install, so the next renderer phase can target a direct NVENC SDK proof instead of another FFmpeg pipe probe.
- FFmpeg CUDA filters are present, but probes show they are not enough for `>8x`, and they do not cover all current VFX filters with parity.
- NVENC fast preset did not improve the real render benchmark, confirming encode preset is not the main bottleneck.
