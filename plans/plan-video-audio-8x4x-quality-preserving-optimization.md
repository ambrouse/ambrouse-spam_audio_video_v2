# Plan: video >8x and audio >4x quality-preserving optimization

Date: 2026-05-16

## Goal

Optimize the real production pipeline so it runs as fast as possible while preserving current video/audio quality, style, timing policy, and effects.

Hard targets:

- Video render must be **more than 8x faster** than the locked current FFmpeg baseline.
- Audio/TTS pipeline must be **more than 4x faster on a first-run cache-miss synthesis** than the locked current real TTS baseline.
- Cache-hit/rerun acceleration is useful but **does not count** as passing the main `>4x` audio target.
- No CPU video fallback.
- No visual effect removal.
- No TTS model, voice, reference, text policy, pause policy, or audio style change unless a benchmark proves the output remains equivalent.
- Work may change language, architecture, renderer, or libraries if the measured gain is worth it.

Current known checkpoint:

- Current FFmpeg 4K60 one-scene benchmark:
  - Artifact: `spam_audio_video/benchmarks/render_4k60/20260516_221957_current_ffmpeg_one_scene_30s/`
  - Duration: `30.0s`
  - Elapsed: `104.298s`
  - Speed: `0.2876x`
  - Encoder: `h264_nvenc`
  - 8x pass threshold from this run: `<= 13.037s`
- Previous native speed-probe:
  - Artifact: `spam_audio_video/benchmarks/native_gpu_4k60/20260516_223237_native_gpu_speed_probe_one_scene_30s/`
  - Elapsed: `25.835s`
  - Multiplier: `3.9755x`
  - Quality failed: SSIM `0.609109`, PSNR `13.960153`
  - Conclusion: it is a speed ceiling probe only, not a production pass.

## Required skills

- `plan-skill`: maintain this file and execute phase by phase.
- `backend-skill`: backend services, pipeline contracts, worker processes, manifests, and failure handling.
- `documentation-skill`: write final architecture and benchmark documentation.
- `logging-skill`: write phase logs and benchmark conclusions under `logs/spam_audio_video/`.
- `testing-skill` if available; if not available, use repo tests, `py_compile`, Rust tests/builds, ffprobe, quality scripts, and real pipeline outputs.
- `frontend-skill` if UI controls are added after backend/runtime proof.
- `push-code-skill` only after all tests, docs, logs, and final quality gates pass.

## Source findings already confirmed

Video bottlenecks:

- `spam_audio_video/auto_generate_video/pipeline.py`
  - `render_video(...)` starts the current render path.
  - Per-clip FFmpeg graph still computes expensive filters such as `boxblur`, `hqdn3d`, `unsharp`, scale/crop, and overlay.
  - Multi-scene output can do `clip encode -> xfade encode -> visual overlay encode`.
  - `_apply_visual_overlays(...)` adds a full-video pass for particles, logo, and optional `showfreqs` audio visualizer.
  - `_build_video_encode_args(...)` correctly uses `h264_nvenc` for GPU encode, but frame generation is still filter/CPU heavy.

Audio bottlenecks:

- `spam_audio_video/auto_text_to_voice/vieneu_worker.py`
  - Current worker loads VoxCPM and calls `self.tts.generate(...)` sequentially per text file.
  - `tts_io_workers` only parallelizes WAV save/postprocess; it does not parallelize model inference.
  - `_merge_wav_files_with_pauses(...)` reads all generated WAV files and writes one combined output after inference.
- VieNeu code has `infer_batch(...)` in several engines, but current production model path is VoxCPM 1.5 VN through the worker, so batch support must be proven, not assumed.

## Output contract

Video must preserve:

- `3840x2160`, `60fps`, H.264 GPU encode.
- Same scene duration policy, default `30s` per image.
- Same scroll/zoom rhythm.
- Same blurred background and foreground panel composition.
- Same palette-derived VFX, particles, logo placement, and audio visualizer behavior.
- Same final mux behavior with AAC audio.

Audio must preserve:

- Same TTS model key and reference voice.
- Same text chunks and chunk order unless the change is explicitly part of a tested chunk policy.
- Same inference settings, pause insertion, trim policy, sample rate, and final combined file contract.
- Same perceived voice, style, pronunciation, and pacing.

## Benchmark artifact policy

Every benchmark must be written into immutable timestamp folders:

```text
spam_audio_video/benchmarks/video_8x4x/{YYYYMMDD_HHMMSS}_{scenario}/
spam_audio_video/benchmarks/audio_8x4x/{YYYYMMDD_HHMMSS}_{scenario}/
spam_audio_video/benchmarks/full_pipeline_8x4x/{YYYYMMDD_HHMMSS}_{scenario}/
```

Each run must include:

- `input/`: copied input manifests, renderer/TTS config, selected files, and hashes.
- `output/`: produced video/audio files.
- `reports/benchmark.json`: elapsed time, multiplier, per-stage timings, pass/fail.
- `reports/quality.json`: metadata and quality checks.
- `reports/summary.md`: human-readable conclusion.
- `logs/`: stdout/stderr, GPU samples, `nvidia-smi`, worker logs.
- `frames/` for video frame samples and diffs.
- `audio_samples/` for sampled WAV chunks, combined WAV, loudness/peak reports, and comparison snippets.

Do not overwrite old benchmark folders.

## Pass gates

Video pass gate:

- Candidate elapsed time `<= baseline_elapsed_s / 8`.
- For current locked one-scene baseline `104.298s`, pass threshold is `<= 13.037s`.
- Metadata exactly matches target: `3840x2160`, `60fps`, duration delta within `<= 1 frame`, hardware H.264.
- `gpu_fallback_used=false`.
- No missing logo, VFX, particles, scroll, or visualizer when audio is present.
- Quality report passes using frame samples and visual inspection notes.
- If native output cannot be pixel-identical due shader implementation, it must pass strict perceptual/frame-diff thresholds and manual output read-through.

Audio pass gate:

- First lock a real baseline using the existing production TTS path.
- Candidate first-run/cache-miss elapsed time `<= audio_baseline_elapsed_s / 4`.
- Same number and order of generated chunks unless cache hits are reusing the exact chunk outputs.
- Combined WAV exists and is playable.
- Sample rate/channel contract preserved.
- Duration delta and inserted pauses match current policy.
- For cache reuse, reused chunks must be binary-identical to the previous valid chunk WAVs.
- For any non-cache inference acceleration, compare representative chunks against baseline using metadata, duration, loudness/peak, speaker/style similarity where possible, and manual listening/read-through.
- Cache-hit results must be reported separately and cannot mark the main audio target as passed.

Full pipeline pass gate:

- Real session output generated from actual project/session inputs.
- Video and audio both pass their own gates.
- Final muxed MP4 has expected video metadata and audio track.
- Benchmark report states whether targets are passed. If either target fails, continue investigation and optimization loop.

## Phase 0: lock baselines and evidence (estimated 2-4 hours)

Steps:

1. Record dirty worktree state and do not revert unrelated changes.
2. Re-run or verify current one-scene 4K60 baseline under `video_8x4x`.
3. Add/run a real audio benchmark harness for `test-1/session_ch0001_to_ch0010`:
   - cold worker load timing;
   - warm worker synthesis timing;
   - per-chunk `infer_ms`;
   - per-chunk `io_ms`;
   - merge timing;
   - output WAV metadata;
   - GPU samples.
4. Write baseline summaries into benchmark folders.

Acceptance:

- Video baseline is locked.
- Audio baseline is locked.
- Reports identify top 3 time consumers for video and audio.

Status 2026-05-16:

- Video baseline was already locked from `spam_audio_video/benchmarks/render_4k60/20260516_221957_current_ffmpeg_one_scene_30s/`.
- Added `spam_audio_video/tools/benchmark_tts_pipeline.py`.
- Audio smoke benchmarks were created under `spam_audio_video/benchmarks/audio_8x4x/`.
- Full-session audio baseline is still pending because only limited real-output smoke runs have been executed so far.

## Phase 1: zero-risk acceleration by exact reuse (estimated 4-8 hours)

Purpose:

- Get guaranteed rerun acceleration without changing output.
- This phase is a supporting optimization only; it cannot satisfy the main first-run `>4x` audio target.

Steps:

1. Add content-addressed TTS cache:
   - key = text bytes + voice profile + reference audio hash + reference text + model key + inference settings + trim/postprocess settings + worker version.
2. Reuse cached per-chunk WAVs when the key matches.
3. Preserve manifest order and combined output behavior.
4. Add cache hit/miss stats to manifest and benchmark reports.
5. Stream/copy cached chunks into output session folder without regenerating them.

Acceptance:

- Cached chunks are binary-identical.
- Real rerun audio benchmark reaches `>4x` when inputs are unchanged, reported as a secondary result.
- Cache miss path still produces the same valid outputs as before.

Status 2026-05-16:

- Implemented content-addressed TTS WAV cache in `vieneu_worker.py`.
- Implemented lazy synth model loading so cache-hit-only runs do not load VoxCPM.
- Implemented VoxCPM prompt/reference cache reuse for generated cache-miss chunks.
- Added cache versioning with `TTS_CACHE_VERSION=2` and folder `tts_cache/v2/`.
- Smoke benchmarks:
  - 1 chunk no-cache: `29.359s`.
  - 1 chunk cache-hit lazy-load: `1.733s`, `16.945x`, pass `>4x`.
  - 3 chunk no-cache: `31.814s`.
  - 3 chunk prompt-cache fresh run: `30.390s`, only a small fresh-run improvement.
  - 3 chunk v2 cache-hit lazy-load: `1.702s`, `18.6969x`, pass `>4x`.
- This does **not** pass the main audio target because the main target requires first-run/cache-miss synthesis.
- Full-session rerun benchmark is still pending.

## Phase 2: audio fresh-run acceleration (estimated 1-2 days)

Purpose:

- Improve first-time TTS generation, not only reruns.

Investigation steps:

1. Inspect installed VoxCPM API for batch or lower-level reusable prompt/reference encodings.
2. Prototype a safe batch path with batch sizes `2`, `3`, `4`, and `6`.
3. If VoxCPM has no true batch API, test:
   - persistent reference embedding/cache if available;
   - phoneme/text preprocessing batch;
   - model warmup and CUDA graph/compile-compatible paths if exposed;
   - one GPU worker only, plus IO workers, to avoid VRAM thrash.
4. Keep `inference_timesteps` and model settings unchanged for quality preservation.
5. Benchmark fresh-run audio against the locked baseline.

Acceptance:

- Fresh-run audio reaches `>4x`.
- Output quality passes representative chunk and combined WAV checks.
- If `>4x` is not reached, continue with Phase 2B:
  - alternative compatible runtime for the same model;
  - TensorRT/ONNX/torch compile only if output equivalence passes;
  - no model swap unless user explicitly accepts a new voice/style.

Status 2026-05-16:

- Public VoxCPM API has no true batch generate method.
- VoxCPM CLI `batch` loops texts sequentially.
- Internal `_inference(...)` accepts batch-shaped tensors, but the shipped generation loop currently checks stop condition from sample `0` and returns `.squeeze(0)`, so direct batching requires a custom private batched inference wrapper with per-sample stop/mask handling.
- Prompt/reference cache reuse gave only a small fresh-run gain and is not enough for `>4x`.
- Next required work is a first-run batch prototype or a compatible compiled/runtime replacement for the same model.
- Parallel worker probe was slower than single worker on RTX 3060.
- Private true-batch probe can run after resizing MiniCPM KV cache, but current stock stop handling is not per sample and output quality/durations fail parity.
- Chunk merging did not provide meaningful speed and risks pacing changes.
- Triton/torch.compile improved per-chunk inference but first-run wall time got worse due compile overhead; compile is now gated behind `SPAM_TTS_TORCH_COMPILE=1`.

## Phase 3: video one-pass FFmpeg cleanup as interim path (estimated 1-2 days)

Purpose:

- Remove wasted encode passes while native zero-copy renderer is being built.

Steps:

1. Precompute per-image static layers:
   - blurred background;
   - sharpened/denoised foreground base;
   - scaled logo variant;
   - palette constants.
2. Fuse visual overlay into the main render path where possible.
3. For multi-scene runs, avoid `clip encode -> xfade encode -> overlay encode` when a single timeline graph can produce the same output.
4. Keep this as a production-safe FFmpeg path if it passes quality.

Acceptance:

- Output passes current visual contract.
- Real benchmark improves over current FFmpeg baseline.
- If it still cannot approach `>8x`, continue to native renderer; this phase is not allowed to redefine success.

Status 2026-05-16:

- FFmpeg CUDA filters are available, but coverage is incomplete for current VFX parity.
- A 5s 4K60 CUDA scale/NVENC probe took `9.234s`, far from `>8x`.
- Changing NVENC preset to `fast` on the real one-scene render took `104.690s` vs baseline `104.298s`; encoder preset is not the bottleneck.
- Continue to native renderer / direct NVENC SDK proof.

## Phase 4: direct native video renderer architecture decision (estimated 4-8 hours)

Purpose:

- Pick the fastest viable native path before writing more renderer code.

Candidates:

- Rust + Direct3D 11/12 or wgpu + direct NVENC SDK.
- C++ + Direct3D 11/12 + NVIDIA Video Codec SDK.
- Rust for orchestration plus C++ FFI encoder if NVENC SDK bindings become the bottleneck.

Decision criteria:

- Direct GPU texture to NVENC or equivalent zero-copy path.
- No CPU frame pipe.
- Can render 4K60 timeline and encode once.
- Can reproduce effects as shaders.
- Build can be packaged for portable Windows.

Expected decision:

- Prefer **C++/Direct3D11 + NVENC SDK** or **Rust + thin C++ NVENC bridge** if the only way to reach `>8x` is zero-copy encode.
- Keep Python as orchestration only.

Acceptance:

- Written architecture note in docs/logs.
- Minimal device/encoder proof creates a valid 4K60 H.264 MP4 from GPU texture input.
- Benchmark proves encoder/device path alone can meet or exceed the `<= 13.037s` video threshold before full shader parity work.

## Phase 5: native video shader parity (estimated 3-7 days)

Purpose:

- Rebuild existing visual style on GPU without changing final appearance.

Steps:

1. Implement timeline parser from `build_native_renderer_input(...)`.
2. Decode/cache source images once.
3. Implement shader stages:
   - background scale/crop/blur/equivalent brightness/saturation;
   - foreground scaling, panel crop, sharpen/denoise equivalent;
   - deterministic scroll/zoom motion;
   - dissolve transitions;
   - palette particles;
   - logo overlay;
   - audio visualizer from precomputed or streamed audio spectrum data.
4. Encode once via direct NVENC path.
5. Emit renderer report with timings for decode, upload, render, encode, mux.

Acceptance:

- One-scene 30s 4K60 passes `>8x`.
- Multi-scene real session passes quality and duration checks.
- Audio visualizer case is tested with real audio, not a synthetic-only clip.

## Phase 6: full pipeline validation on real outputs (estimated 1-2 days)

Steps:

1. Run real audio baseline and candidate on `test-1/session_ch0001_to_ch0010`.
2. Read/validate generated `tts_inputs`, per-chunk WAVs, combined WAV, and manifest.
3. Run real video baseline and candidate with the same source images and audio.
4. Read/validate final MP4 metadata, sampled frames, VFX presence, logo placement, visualizer presence, audio track, and mux duration.
5. Store all evidence under benchmark folders.

Acceptance:

- Video `>8x` pass.
- Audio `>4x` pass.
- Full muxed output passes quality.
- Reports explicitly say `target_pass=true`.

## Phase 7: integration and controls (estimated 1 day)

Steps:

1. Add backend renderer selection:
   - current FFmpeg stable path;
   - native fast path only when available and quality gate is enabled.
2. Add fail-loud behavior:
   - no silent CPU fallback;
   - no silent fallback from native to FFmpeg in benchmark mode;
   - if native fails quality gate, report failure and preserve artifacts.
3. Add frontend controls only after backend proof:
   - renderer selection;
   - benchmark run;
   - audio cache stats;
   - target pass/fail summary.

Acceptance:

- Existing UI behavior remains compatible.
- New controls reflect real runtime status.
- Benchmark mode cannot hide failures.

## Phase 8: cleanup, docs, and logs (estimated 4-8 hours)

Steps:

1. Remove dead experiments and unused source files.
2. Keep native renderer folder clean and documented.
3. Update docs:
   - renderer architecture;
   - audio cache/batch behavior;
   - benchmark interpretation;
   - portable Windows implications.
4. Write implementation log under `logs/spam_audio_video/`.
5. Run targeted tests and final real benchmark.

Acceptance:

- No unneeded generated build output in source.
- Docs and logs point to final benchmark artifacts.
- Final summary includes exact elapsed times and multipliers.

## Optimization loop if targets fail

If video does not reach `>8x`:

1. Profile native renderer stage timings.
2. Identify whether bottleneck is decode/upload, shader render, readback, encode, mux, or disk.
3. Replace the slowest stage and rerun benchmark.
4. Repeat until `target_pass=true` or hardware limit is proven by isolated stage benchmarks.

If audio does not reach `>4x`:

1. Profile load, preprocess, inference, trim, save/postprocess, and merge.
2. Optimize the slowest stage.
3. Rerun real audio benchmark and quality checks.
4. Repeat until `target_pass=true` or model/runtime limit is proven.

The task is not considered complete until both target gates pass on real outputs.
