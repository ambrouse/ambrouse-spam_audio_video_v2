# 2026-05-16 Video/Audio 8x4x Optimization

## Scope

Started executing `plans/plan-video-audio-8x4x-quality-preserving-optimization.md`.

## Code Changes

- Added TTS content-addressed WAV cache inside `spam_audio_video/auto_text_to_voice/vieneu_worker.py`.
- Added lazy model loading for TTS synth:
  - cache-hit-only runs do not load VoxCPM;
  - model loads only when at least one chunk is a cache miss.
- Added VoxCPM prompt/reference cache reuse for cache misses so the worker does not rebuild the same prompt cache for every generated chunk.
- Added cache versioning (`TTS_CACHE_VERSION=2`) and cache folder versioning under `tts_cache/v2/` so future worker logic changes cannot silently reuse stale cache keys.
- Updated `benchmark_tts_pipeline.py` so the main target field is `main_first_run_pass_4x`; cache-hit runs can no longer be mistaken for the main audio pass.
- Added `tts_cache_enabled` and `cache_root` payload plumbing in `spam_audio_video/source_full/backend/pipeline_service.py`.
- Added `spam_audio_video/tools/benchmark_tts_pipeline.py` with artifact folders, WAV metadata, worker log parsing, cache stats, and target pass/fail reporting.

## Validation

- `python -m py_compile spam_audio_video/auto_text_to_voice/vieneu_worker.py spam_audio_video/source_full/backend/pipeline_service.py spam_audio_video/tools/benchmark_tts_pipeline.py` passed.
- `python -m unittest spam_audio_video.tests.test_tts_chunk_policy` passed.
- `cargo fmt --check && cargo build --release` passed in the renderer crate. The production path later moved this crate to `spam_audio_video/renderers/story_gpu_renderer`.

## Real Audio Smoke Benchmarks

Artifact root:

- `spam_audio_video/benchmarks/audio_8x4x/`

Runs:

- `20260516_225632_smoke_no_cache_1_chunk`
  - elapsed: `29.359s`
  - combined WAV: `8.267s`, `44100 Hz`, mono
  - infer total: `6712ms`
- `20260516_225832_smoke_cache_hit_lazy_load_1_chunk`
  - elapsed: `1.733s`
  - cache hits/misses: `1/0`
  - multiplier vs 1-chunk no-cache baseline: `16.945x`
  - pass 4x: `true`
- `20260516_225959_smoke_no_cache_3_chunks`
  - elapsed: `31.814s`
  - combined WAV: `26.365s`, `44100 Hz`, mono
  - infer total: `19537ms`
- `20260516_230256_smoke_no_cache_prompt_cache_3_chunks`
  - elapsed: `30.390s`
  - infer total: `18218ms`
  - fresh-run improvement vs previous 3-chunk no-cache: about `1.05x` total, `1.07x` inference
- `20260516_230358_smoke_v2_cache_populate_3_chunks`
  - elapsed: `31.167s`
  - cache version: `2`
- `20260516_230435_smoke_v2_cache_hit_3_chunks`
  - elapsed: `1.731s`
  - cache hits/misses: `3/0`
  - multiplier vs 3-chunk no-cache run: `18.3826x`
  - pass 4x: `true`
- `20260516_230527_smoke_v2_folder_cache_populate_3_chunks`
  - elapsed: `30.083s`
  - cache path folder: `tts_cache/v2/`
- `20260516_230602_smoke_v2_folder_cache_hit_3_chunks`
  - elapsed: `1.702s`
  - cache hits/misses: `3/0`
  - multiplier vs 3-chunk no-cache run: `18.6969x`
  - pass 4x: `true`

## Current Status

- Audio cache-rerun path exceeds `>4x` on smoke tests while preserving output by reusing exact cached WAVs.
- Per user clarification, cache-rerun does **not** count as passing the main audio target. The main target is first-run/cache-miss synthesis `>4x`.
- Fresh-run audio acceleration improved only slightly; current inference remains sequential per cache miss and does not reach `>4x`.
- Video `>8x` is not solved yet; previous native probe still fails quality and only reached about `3.98x`.
- Native video environment check:
  - `C:\Windows\System32\nvEncodeAPI64.dll` exists.
  - `D:\appSetting\unreal_engine\UE_5.5\Engine\Source\ThirdParty\NVIDIA\nvEncode\nvEncodeAPI.h` exists.
  - Current Rust native crate still only runs the FFmpeg/NVENC speed probe.

## Video Investigation

- FFmpeg build supports CUDA filters:
  - `scale_cuda`
  - `overlay_cuda`
  - `bilateral_cuda`
  - `colorspace_cuda`
  - `hwupload_cuda`
- FFmpeg build does not provide CUDA equivalents for every current production effect:
  - no direct CUDA `boxblur`;
  - no direct CUDA `unsharp`;
  - no direct CUDA `hqdn3d`;
  - `showfreqs` visualizer remains CPU/filter based.
- CUDA filter speed probe:
  - `cuda_filter_probe_5s.mp4`
  - 5 seconds 4K60 took `9.234s`.
  - This is not close to `>8x` and does not include full VFX parity.
- NVENC preset probe:
  - `20260516_233320_current_ffmpeg_fast_preset_one_scene_30s_fast_preset`
  - one-scene 30s 4K60 with `video_preset=fast` took `104.690s`.
  - Baseline quality preset was `104.298s`.
  - Conclusion: encoder preset is not the bottleneck; FFmpeg frame generation/effects are.

## Fresh-Run Audio Investigation

- Public VoxCPM API exposes `generate(...)` and `generate_streaming(...)`, but no true batch method.
- VoxCPM CLI `batch` reads many lines but loops and calls `tts.generate(...)` per text.
- Internal `VoxCPMModel._inference(...)` accepts batch-shaped tensors, which means a real batch prototype may be possible.
- The shipped generation wrapper is not batch-safe as-is:
  - stop condition checks sample `0`;
  - non-streaming output squeezes batch dimension `0`;
  - variable-length early stop requires custom per-sample active masks.
- Prompt/reference cache reuse was implemented and tested, but fresh-run speed only improved from `31.814s` to `30.390s` on the 3-chunk smoke, far from `>4x`.
- Parallel multi-worker probe:
  - `20260516_231737_first_run_parallel_probe_2w_4chunks`
  - 2 workers / 4 chunks took `51.669s`.
  - Single worker / 4 chunks took `39.024s`.
  - Conclusion: multiple model instances contend for the RTX 3060 and slow down first-run synthesis.
- Private true-batch VoxCPM probe:
  - Initial B=2 failed because MiniCPM KV cache was initialized for batch size 1.
  - After calling `setup_cache(batch_size, ...)`, B=2 and B=4 ran.
  - B=4 reported `load_s=9.644s`, `infer_decode_s=20.427s`.
  - Quality is not passable yet because stock stop handling observes sample 0 and all batch outputs had the same duration.
  - Speed is still far below `>4x`.
- Chunk merge probe:
  - Merging 4 text chunks into 1 TTS input took `37.120s` vs `39.024s` baseline.
  - Conclusion: not enough speed, and it risks changing pacing.
- Triton/torch.compile probe:
  - Installed `triton-windows==3.7.0.post26`.
  - With compile enabled implicitly, 4 chunks took `151.963s` first run and `58.624s` second run because compile overhead dominates.
  - Inference-only time improved, but first-run wall time failed the target badly.
  - Production worker now gates compile behind `SPAM_TTS_TORCH_COMPILE=1` and defaults compile off.
  - Compile-off 4 chunk run after the gate: `34.725s`, still only `1.1238x` vs the `39.024s` local baseline and not `>4x`.

## Next Steps

1. Run full-session audio baseline/cache benchmark after deciding whether to spend the long runtime now or after fresh-run improvements.
2. Continue investigating compatible runtime/model execution replacements; current VoxCPM first-run paths tested so far do not approach `>4x`.
3. Continue video path with direct GPU texture-to-NVENC proof, because FFmpeg pipe/filter path is still below target.
