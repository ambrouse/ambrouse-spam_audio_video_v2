# Plan: fastest 4K60 render pipeline with unchanged video/audio output

Date: 2026-05-16

## Goal

Rebuild or optimize the current TTS and video render pipeline so production output remains the same in quality and style while render speed becomes as fast as realistically possible.

Non-negotiable output requirements:

- Final video stays 4K, 60fps, H.264 hardware encoded, same visual style, same motion behavior, same logo placement, same VFX/audio visualizer intent, same audio mux behavior.
- Default video `Seconds per image` becomes 30 seconds for the production workflow while preserving 4K60 output and current visual style.
- Audio output stays the same model, voice profile behavior, sample content, and postprocess defaults.
- TTS input punctuation and chunking policy is intentionally tightened:
  - exported `tts_inputs/text_*.txt` must remove commas and keep only periods as punctuation;
  - chunking must use periods as the only natural boundary;
  - comma must never act as a chunk boundary;
  - default minimum chunk size must be at least 30 words;
  - frontend must allow the user to adjust the minimum chunk words, but clamp it to 30 or higher for this production workflow.
  The TTS voice/model/quality must remain unchanged, but pause behavior must be revalidated because comma pauses will no longer be present in generated TTS input text.
- No silent CPU encoder fallback. If GPU encode/runtime is unavailable, fail loudly with a clear diagnostic.
- Any new algorithm, library, language, or renderer must prove it is faster with a repeatable benchmark before replacing the current production path.
- The benchmark must be committed as a concrete file so future changes can show whether render is faster or slower.
- Browser automation must keep Gemini and GPT port selection separate:
  - Gemini rewrite and Gemini image-prompt writing use only the Gemini-selected ports;
  - GPT image generation uses only the GPT-selected ports;
  - both still share the same Browser Bridge base URL/server;
  - existing parallel pipeline behavior must be preserved;
  - before a Gemini phase starts, ping/warm the selected Gemini ports once through the bridge server;
  - before a GPT phase starts, ping/warm the selected GPT ports once through the bridge server;
  - fixes to browser automation behavior belong in `toll-brouser-gpt-gemini`, not as brittle workarounds in `spam_audio_video`.

## Current suspected bottleneck

The current video path already uses `h264_nvenc` for final H.264 encoding, so the main slowdown is not CPU video encoding. The heavy cost is FFmpeg CPU-side frame generation at 4K60:

- per-frame scale/crop/pan;
- background blur;
- denoise/sharpen;
- overlay composition;
- xfade transition;
- VFX/audio visualizer pass;
- multiple FFmpeg clip workers running at the same time.

At 4K60, one 60 second scene is 3,600 frames. Any filter repeated per frame becomes expensive quickly.

## Skills used

- `plan-skill`: create this detailed task plan in `plans/` before implementation.
- `project-workflow`: follow repository workflow and existing pipeline conventions.
- `backend-skill`: modify Python backend/render/TTS services cleanly.
- `frontend-skill`: update chunk controls and worker controls so frontend values are real production inputs with safe fast defaults.
- `testing-skill`: required during implementation for benchmark validation, regression tests, and smoke renders. If no local testing skill file is available in the active session, use repo-local test conventions and document the fallback.
- `documentation-skill`: document final architecture, benchmark interpretation, and operational guidance.
- `logging-skill`: log each implementation phase and benchmark result.
- `push-code-skill`: after implementation is complete, reviewed, documented, tested, committed, and pushed.

## Phase 1: Quality contract and source review (estimated 45 minutes)

1. Read the current render and TTS pipeline:
   - `spam_audio_video/auto_generate_video/pipeline.py`
   - `spam_audio_video/source_full/backend/video_service.py`
   - `spam_audio_video/source_full/backend/pipeline_service.py`
   - `spam_audio_video/auto_text_to_voice/vieneu_worker.py`
2. Extract the current production render contract:
   - resolution: 3840x2160 when GPT image workflow requests landscape 4K;
   - fps: current production path forces 60fps;
   - current seconds per image is 60, target production default must become 30;
   - encoder: `h264_nvenc` through `VIDEO_ENCODER=auto`;
   - encoder settings: preset, CQ, GOP, pix_fmt;
   - motion math: scroll amplitude, zoom, crop, side padding;
   - overlay behavior: background, foreground panel, logo, particles, visualizer, audio mux.
3. Extract the current TTS contract:
   - model key and runtime device policy;
   - voice profile discovery;
   - inference settings;
   - WAV generation;
   - pause insertion;
   - TTS text export path and punctuation rules;
   - optional postprocess behavior;
   - manifest fields.
4. Review the current TTS text preparation path:
   - `spam_audio_video/auto_convert_text/pipeline/audio_cleaner.py`
     - current `clean_for_audio(...)` keeps `.` and `,`;
     - this phase must decide whether commas are removed at audio-clean time or only at TTS export time.
   - `spam_audio_video/auto_convert_text/pipeline/simple_chunker.py`
     - current `_split_pause_pieces(...)` splits on `[.,]`;
     - current chunk and `tts_inputs` files preserve comma endings;
     - new production chunking must split naturally only on `.`;
     - comma must be treated as removable punctuation/spacing, not a boundary;
     - new production `tts_inputs/text_*.txt` must contain no commas.
   - `spam_audio_video/source_full/backend/convert_service.py`
     - `export_tts_text(...)` delegates to `chunk(...)`, so chunk/export behavior must stay consistent.
   - `spam_audio_video/source_full/backend/pipeline_service.py`
     - `_auto_export_session_tts_inputs_from_audio_clean(...)` fallback must also remove commas and keep periods only.
5. Review current frontend/backend controls that affect speed and TTS chunking:
   - `spam_audio_video/source_full/frontend/index.html`
     - `chunkMinWordsInput` currently allows `min=1` and default `16`;
     - `chunkMaxWordsInput` currently allows `min=1` and default `64`;
     - `ttsIoWorkersInput` currently allows `1-6` and default `2`;
     - `rewriteWorkersInput` currently allows `1-9` and default `2`.
   - `spam_audio_video/source_full/frontend/app.js`
     - `CHUNK_PRESETS` currently use `16/20/24` minimum words;
     - `runCreateTtsInputs()` sends `min_words` and `max_words`;
     - `currentRewriteConfig()` sends `parallel_workers`;
     - run-all payload sends `tts_io_workers`.
   - `spam_audio_video/source_full/backend/server.py`
     - `ConvertChunkRequest` currently defaults to `min_words=16`, `max_words=64`;
     - run-all defaults `parallel_workers=2`, `tts_io_workers=2`;
     - rewrite and TTS worker fields must remain wired from frontend payloads.
   - `spam_audio_video/source_full/backend/pipeline_service.py`
     - TTS IO workers are clamped to `1..6`;
     - benchmark must confirm whether default should be 6 or a lower stable value on the current machine.
6. Review browser bridge and provider-port routing:
   - `spam_audio_video/auto_convert_text/pipeline/browser_bridge_client.py`
     - `chat(...)` and `image(...)` already support a `ports` list in payload;
     - `ping_ports(...)` supports pinging a specific list of ports.
   - `spam_audio_video/source_full/frontend/index.html`
     - generic `Browser Bridge Ports` exists;
     - GPT video tab has `videoGptPortsInput`;
     - Gemini tab currently does not expose a separate production Gemini port selector and mostly points users back to the Bridge tab.
   - `spam_audio_video/source_full/frontend/app.js`
     - `parseGeminiPorts()` reads the generic bridge ports;
     - `parseGptPorts()` currently prioritizes generic bridge ports before `videoGptPortsInput`, which prevents true GPT-only port selection;
     - `buildVideoPayload()` passes one `cdp_urls` list, currently used by both Gemini prompt generation and GPT image generation.
   - `spam_audio_video/auto_generate_video/pipeline.py`
     - `generate_prompts(...)` uses `_bridge_ports_from_config(config)` for Gemini prompt writing;
     - `_generate_images_via_bridge_gpt(...)` uses the same `_bridge_ports_from_config(config)` for GPT image creation;
     - config must be split into Gemini bridge ports and GPT bridge ports while preserving backwards compatibility with existing `cdp_urls`.
   - `toll-brouser-gpt-gemini/examples/apps/gemini-use/server.py`
     - `/v1/chat/gemini`, `/v1/chat/gpt`, `/v1/image/gemini`, and `/v1/image/gpt` accept `ports`;
     - `/v1/ports/ping` accepts a `ports` list and probes status;
     - `/v1/web/open` currently opens through the Gemini service for all ports, so provider-specific warm/open behavior must be verified and fixed in this repo if needed;
     - current port scheduler is shared across providers, preserving cross-provider port locking.
7. Define measurable "unchanged output" checks:
   - video duration delta <= 1 frame unless source audio duration changes;
   - frame size exactly 3840x2160;
   - frame rate exactly 60/1 or equivalent 60fps stream metadata;
   - audio sample rate/channel/codec unchanged after mux;
   - encoder remains hardware H.264, preferably `h264_nvenc`;
   - selected keyframes from old/new render pass SSIM >= 0.995 for algorithm-preserving paths, or documented pixel-identical expectation if the path is mathematically equivalent;
   - audio waveform hash unchanged for fixed TTS input files when render-only code changes;
   - when the punctuation policy change is implemented, compare audio metadata and subjective sample quality instead of requiring waveform hash equality, because removing commas from TTS text can legitimately change pauses.
8. Define measurable TTS punctuation and chunking checks:
   - every exported `tts_inputs/text_*.txt` contains no comma characters;
   - periods are preserved as sentence-ending punctuation;
   - natural chunk boundaries are periods only;
   - no chunk is ended solely because of a comma;
   - configured `min_words` defaults to at least 30;
   - frontend and backend both clamp production `min_words` to 30 or higher;
   - no exported file ends without a period unless it is intentionally empty/invalid and skipped;
   - chunk word counts remain within the configured min/max bounds where possible;
   - manifest records the punctuation policy used for traceability.
9. Define measurable frontend worker-control checks:
   - changing `TTS IO workers (save/postprocess)` in the UI changes the backend `tts_io_workers` payload and worker `io_workers` manifest/log value;
   - changing `Rewrite workers` in the UI changes the backend `parallel_workers` payload and rewrite manifest `parallel_workers`;
   - defaults are set to the largest stable values proven by local benchmark, not arbitrary small values;
   - UI max values match backend clamp values so the user cannot select numbers that are ignored.
10. Define measurable browser bridge port-routing checks:
   - Gemini rewrite uses only selected Gemini ports;
   - Gemini video prompt writing uses only selected Gemini ports;
   - GPT image creation uses only selected GPT ports;
   - ping/warm is called once for Gemini ports before Gemini rewrite/prompt phases;
   - ping/warm is called once for GPT ports before GPT image phase;
   - bridge status output records selected provider, selected ports, active ports, and used port per item;
   - if GPT image generation returns text or no valid image asset, the bridge reports a provider-level image error and the pipeline retries/fails clearly instead of saving text as an image or silently accepting the response.

Expected output:

- A written quality contract inside the benchmark/config code and final documentation.
- Clear list of fields that must remain stable in `render_manifest.json` and audio manifest.
- Clear TTS punctuation/chunking contract: commas removed, periods preserved, period-only natural chunk boundaries, minimum chunk words 30+.
- Clear worker-control contract: frontend values must be real, benchmarked, and visible in manifests/logs.
- Clear provider-port routing contract: Gemini and GPT can share the bridge server but must not share an implicit port list unless the user explicitly configures the same ports in both selectors.

## Phase 2: Benchmark harness first (estimated 2 hours)

Create a benchmark file before changing production render code.

Planned benchmark file:

- `spam_audio_video/tools/benchmark_4k60_render.py`

Benchmark responsibilities:

1. Accept a real project/session or a prepared fixture:
   - `--project-id`
   - `--session-id`
   - `--seconds`
   - `--scenes`
   - `--width 3840`
   - `--height 2160`
   - `--fps 60`
   - `--renderer current|precompute-ffmpeg|cuda-ffmpeg|native-gpu`
2. Run a deterministic short render:
   - recommended default: 3 scenes x 10 seconds at 4K60;
   - production benchmark: 10 scenes x 60 seconds at 4K60 when time allows.
3. Collect speed metrics:
   - wall time;
   - rendered video seconds per wall second;
   - average output fps;
   - per-stage timings: layer preparation, clip render, transition, visual overlay, mux;
   - process peak memory if available;
   - CPU/GPU/NVENC samples if `nvidia-smi` is available.
4. Collect quality metrics:
   - ffprobe stream metadata;
   - duration;
   - frame count estimate;
   - encoder name;
   - selected-frame SSIM/PSNR against baseline when comparing two renderers;
   - audio stream metadata and audio hash when applicable.
5. Write benchmark artifacts:
   - `spam_audio_video/projects_workspace/runtime/benchmarks/render_4k60/{timestamp}/result.json`
   - `.../summary.md`
   - optional stderr/stdout logs for each renderer run.
6. Include scene-duration metadata:
   - production default target is 30 seconds per image;
   - benchmark output must record requested seconds per image, actual per-image duration, total scene count, and final duration.

Acceptance for the benchmark harness:

- It can benchmark the current renderer without modifying production behavior.
- It produces a machine-readable `result.json`.
- It clearly marks pass/fail for 4K60 metadata and hardware encoder checks.
- It can compare a new renderer against the current renderer.

Expected output:

- Repeatable benchmark file exists before optimization work starts.
- Baseline current-pipeline numbers are captured.
- Benchmark reports clearly whether it used 30 seconds per image or a shorter smoke-test override.

## Phase 2.5: Browser Bridge provider-port split and warmup plan (estimated 3-5 hours)

Separate Gemini and GPT port routing while keeping the existing parallel pipeline behavior.

1. Update frontend port configuration:
   - keep one shared `Bridge base URL`;
   - keep generic `Browser Bridge Ports` as a convenience/default field;
   - add or expose a dedicated Gemini ports field for rewrite and Gemini video prompt writing;
   - keep dedicated GPT ports field for GPT image creation;
   - change `parseGeminiPorts()` so it reads Gemini-selected ports first, then falls back to generic bridge ports;
   - change `parseGptPorts()` so it reads GPT-selected ports first, then falls back to generic bridge ports;
   - do not let generic bridge ports overwrite GPT ports unless the GPT field is empty.
2. Split backend/pipeline config:
   - add explicit Gemini bridge port fields, for example `gemini_cdp_url/gemini_cdp_urls`;
   - keep GPT bridge port fields, for example `gpt_cdp_url/gpt_cdp_urls`;
   - preserve backwards compatibility: old `cdp_url/cdp_urls` can be treated as both Gemini and GPT ports only when explicit provider-specific lists are absent;
   - record both selected lists in video manifests.
3. Apply provider-specific ports:
   - rewrite phase uses Gemini ports from current rewrite config;
   - `generate_prompts(...)` uses Gemini ports only;
   - `_generate_images_via_bridge_gpt(...)` uses GPT ports only;
   - prompt/image parallel dispatch remains unchanged except for the candidate port lists.
4. Add phase warmup/ping:
   - before Gemini rewrite starts, call bridge status/ping once with Gemini ports;
   - before Gemini video prompt writing starts, call bridge status/ping once with Gemini ports;
   - before GPT image generation starts, call bridge status/ping once with GPT ports;
   - if ping returns inactive ports, fail or warn according to the existing bridge-open workflow; do not silently route to a different provider's ports.
5. Verify and fix bridge behavior in `toll-brouser-gpt-gemini`:
   - inspect whether `/v1/ports/ping` only probes or also registers/warms ports as the pipeline expects;
   - if ping does not warm/register enough for provider phases, implement the correct behavior in the bridge server or add a provider-aware warm endpoint there;
   - `/v1/web/open` currently opens via Gemini service only, so add provider-aware open/warm behavior if GPT ports need a GPT tab prepared;
   - update bridge tests in `toll-brouser-gpt-gemini/tests/ci/` for provider-specific port lists.
6. Handle GPT image returning text instead of image:
   - harden `toll-brouser-gpt-gemini` image flow so text-only responses, markdown, HTML, links without downloadable image assets, or "I cannot generate" answers are classified as image-generation failure;
   - return clear error codes such as `IMAGE_TEXT_RESPONSE`, `IMAGE_NO_ASSET`, or `IMAGE_TOOL_NOT_ACTIVE`;
   - keep retry/failover across GPT ports as currently designed;
   - make `spam_audio_video` fail clearly when all GPT image attempts return text/no asset.

Acceptance criteria:

- Gemini rewrite/prompt requests never use GPT-only ports.
- GPT image requests never use Gemini-only ports.
- Selecting the same port list for both providers still works.
- Ping/warm is run once per provider phase and logged.
- Browser bridge manifests/results show `provider`, selected ports, used port, and request id.
- GPT text-only image responses are never treated as successful images.

Expected output:

- Provider-specific port routing is deterministic and debuggable.
- Any browser automation fixes live in `toll-brouser-gpt-gemini`, with tests there.

## Phase 3: Algorithm bake-off design (estimated 1 hour)

Evaluate competing approaches with the same benchmark and quality contract. Do not replace production until a candidate proves speed and output stability.

Candidate A: current FFmpeg pipeline baseline

- Keep current implementation unchanged.
- Purpose: baseline speed and quality reference.

Candidate B: FFmpeg precomputed layer renderer

- Precompute each static scene into reusable still layers:
  - blurred 4K background;
  - sharpened/denoised foreground source at the required overscan size;
  - optional logo prepared at final display size.
- Move `boxblur`, `hqdn3d`, `unsharp`, and static scaling out of the per-frame 60fps filter chain.
- Per-frame render keeps only crop/pan, final scale if needed, overlay, fps, and encode.
- Keep FFmpeg/NVENC and current visual math.

Expected benefit:

- High likelihood of major speedup with low visual risk.
- Best first implementation candidate because it preserves the current visual style almost exactly.

Candidate C: FFmpeg CUDA/Vulkan/libplacebo renderer

- Probe the active FFmpeg build for:
  - `scale_cuda`
  - `scale_npp`
  - `overlay_cuda`
  - `hwupload_cuda`
  - `libplacebo`
  - Vulkan filters if available.
- Build a proof-of-concept GPU filter graph only if the installed FFmpeg supports the required filters.
- Keep the same motion math and output encoder.

Expected benefit:

- Potentially faster than CPU filters.
- Risk: Windows FFmpeg build may not include the needed filters, and GPU upload/download can erase gains.

Candidate D: native GPU compositor

- Prototype a dedicated GPU compositor if FFmpeg filters remain the bottleneck:
  - Rust + `wgpu` + FFmpeg/NVENC handoff;
  - C++ Direct3D11/12 + NVENC SDK;
  - Python orchestration with a compiled renderer binary.
- Render scene animation with GPU textured quads:
  - background layer;
  - foreground layer;
  - logo layer;
  - particle/visualizer layers if reproducible.
- Encode through NVENC without CPU-side full-frame filtering.

Expected benefit:

- Highest long-term performance ceiling.
- Highest engineering cost and regression risk.

Candidate E: hybrid native frame server

- Use a renderer process to generate frames through GPU and pipe raw frames to FFmpeg NVENC.
- Avoid writing huge intermediate image sequences.
- Benchmark pipe overhead at 4K60 before committing.

Expected benefit:

- Easier integration than full NVENC SDK, but may still be bottlenecked by CPU copy bandwidth.

Decision rule:

- Implement Candidate B first unless benchmark proves it is not meaningfully faster.
- Move to Candidate C if local FFmpeg supports enough GPU filters and benchmark shows a clear improvement.
- Move to Candidate D only if Candidate B/C cannot meet speed goals and the benchmark shows CPU frame filtering remains dominant.

Expected output:

- A short architecture decision record in docs after benchmark results.

## Phase 4: Implement Candidate B precomputed layer renderer (estimated 4-6 hours)

1. Add a renderer abstraction without changing the API:
   - keep current renderer available as `current`;
   - add new renderer as `precompute-ffmpeg`;
   - select through config/env only after benchmark passes.
2. Add layer preparation helpers:
   - generate deterministic per-scene cached assets under the session render cache;
   - include source image hash, output dimensions, motion settings, and filter settings in cache key;
   - invalidate cache when source image or render settings change.
3. Precompute static filters once per scene:
   - background: scale/crop/blur/eq into final 4K background image or lossless short video if faster;
   - foreground: upscale/denoise/sharpen into overscan image;
   - logo: scale once if logo exists.
4. Rewrite per-frame clip render filter:
   - use prepared background and foreground;
   - apply only animated crop/pan and final overlay per frame;
   - keep exact motion math from current pipeline;
   - encode with the same `h264_nvenc` settings.
5. Preserve manifests:
   - include renderer name;
   - include cache hits/misses;
   - include benchmark timings per stage;
   - include selected encoder and no fallback reason.

Acceptance criteria:

- 4K60 output metadata matches baseline.
- Visual style is unchanged by inspection and SSIM/PSNR checks.
- Current render path remains available until the new path passes all benchmarks.
- No CPU encoder fallback is introduced.

Expected output:

- A faster renderer with low visual risk.
- Benchmark can compare `current` vs `precompute-ffmpeg`.

## Phase 5: Optimize final passes and transitions (estimated 3-5 hours)

1. Profile whether xfade or visual overlay pass is now the bottleneck.
2. If safe, combine passes:
   - xfade plus logo/VFX/visualizer in one final graph;
   - or keep separate if combined graph is slower or changes output.
3. Cache or pre-render VFX layers when deterministic:
   - particle layer as alpha video;
   - visualizer remains audio-dependent and may stay in final pass.
4. Keep audio mux as stream copy for video and AAC encode for audio as current behavior requires.

Acceptance criteria:

- No visible style change.
- Final audio mux behavior unchanged.
- Benchmark shows improvement or the attempted optimization is rejected and documented.

Expected output:

- Reduced duplicate decode/filter/encode work where safe.

## Phase 6: TTS punctuation and performance audit without model quality change (estimated 2-3 hours)

Do not change TTS model behavior unless benchmark shows a non-audio-quality bottleneck. The intentional TTS text behavior changes in this plan are: remove commas from exported TTS input files, keep periods only, use periods as the only natural chunk boundary, and require production minimum chunk size of 30 words or higher.

1. Confirm TTS runtime:
   - CUDA device selected;
   - CPU-only torch fails loudly;
   - manifest contains `device=cuda`.
2. Implement and verify the TTS punctuation/chunking policy before audio synthesis:
   - update `clean_for_audio(...)` or the chunk/export layer so commas are removed before writing `tts_inputs/text_*.txt`;
   - keep periods as the only punctuation retained in exported TTS input text;
   - change `_split_pause_pieces(...)` into a period-only sentence splitter, or add a new clearly named period-only splitter;
   - ensure comma never creates a `TextPiece` boundary and never forces `flush_chunk(...)`;
   - set backend defaults to `min_words=30` and a conservative `max_words` such as `60` or `64`, then benchmark sample quality;
   - enforce `min_words = max(30, requested_min_words)` in the production chunk/export path;
   - if a period-delimited sentence is shorter than 30 words, merge it with following period-delimited sentences until the minimum is reached where possible;
   - if one period-delimited sentence exceeds `max_words`, split by word count as a forced fallback and append a period to the forced chunk;
   - update `chunk_*.txt` and `tts_inputs/text_*.txt` together so both follow the same period-only/no-comma policy;
   - update `_auto_export_session_tts_inputs_from_audio_clean(...)` so fallback-generated TTS input files follow the same no-comma policy;
   - update chunk manifest with `punctuation_policy`, for example `period_only_no_commas`, plus `natural_boundary=period`, `min_words_effective`, and `forced_word_limit_splits`.
3. Add punctuation tests:
   - direct unit tests for `clean_for_audio(...)` with Vietnamese text containing commas;
   - chunker tests proving exported `tts_inputs/text_*.txt` files contain periods but no commas;
   - chunker tests proving comma does not split a chunk;
   - chunker tests proving normal chunks are at least 30 words when enough source text exists;
   - long-sentence tests proving forced word-limit splits end with periods;
   - fallback auto-export test proving no commas are written when chunk files are missing;
   - regression sample using text like `Thiên Đấu đế quốc, Thánh Hồn thôn. Ngày hôm nay...` should export without the comma and keep sentence periods.
4. Benchmark TTS stages separately:
   - model load/prewarm;
   - per-file inference;
   - WAV write;
   - edge trim;
   - postprocess;
   - final WAV merge.
5. Optimize only non-inference plumbing first:
   - keep persistent worker warm;
   - avoid repeated model reload;
   - batch metadata/file operations where safe;
   - parallelize WAV writes only to the point that it does not disturb ordering.
6. Do not change:
   - voice profile;
   - model key;
   - inference timesteps;
   - denoise/normalize defaults;
   - postprocess default.
7. Revalidate pause behavior:
   - because commas are removed, comma-based shorter pauses should not be expected from TTS input text;
   - period-only text should make TTS cadence more sentence-stable;
   - if old comma pauses are still required for timing while final text has no commas, store pause intent in metadata instead of punctuation and apply it during WAV merge, but do not reintroduce commas into `tts_inputs`.

Acceptance criteria:

- Audio waveform for an identical fixed input remains unchanged when no TTS settings change.
- For the new punctuation/chunking policy, exported text files contain no commas, keep periods, split naturally only on periods, and use effective `min_words >= 30`.
- Commas do not appear in `chunks` or `tts_inputs`.
- Audio model/voice/sample settings remain unchanged.
- TTS manifest stays compatible.
- Chunk manifest records the punctuation policy and counts any files sanitized.
- Any speed gain is documented separately from video render gains.

Expected output:

- Confidence that TTS is not secretly falling back to CPU.
- Confidence that `tts_inputs` never reintroduces commas or comma-boundary chunking through chunk/export/fallback paths.
- Optional non-quality TTS speedups.

## Phase 6.5: Frontend chunk and worker controls (estimated 2-3 hours)

Make the frontend controls real, safe, and tuned for fastest stable throughput on the current infrastructure.

1. Update video duration control:
   - set `VIDEO_PROD_PRESET.scene_duration_seconds` to `30`;
   - set `videoSceneDurationInput` default value to `30`;
   - update backend video defaults in request models/services from `60.0` to `30.0` where they represent production UI defaults;
   - preserve explicit user override when the frontend sends another valid seconds-per-image value;
   - record requested/effective seconds per image in analysis/render manifests.
2. Update chunk controls:
   - set `chunkMinWordsInput` HTML minimum to `30`;
   - set default min words to `30`;
   - update `CHUNK_PRESETS` so all presets use min words >= 30;
   - keep max words adjustable from frontend;
   - validate in `runCreateTtsInputs()` before sending payload:
     - `min_words = max(30, floor(input))`;
     - `max_words = max(min_words, floor(input))`;
   - show the effective range back in UI status so the user sees the actual values.
3. Update backend defaults and clamps:
   - `ConvertChunkRequest.min_words` default becomes `30`;
   - `DEFAULT_TTS_MIN_WORDS` becomes `30`;
   - full-run chunk step uses the same defaults;
   - backend clamps requested min words to 30+ even if an old frontend sends a smaller value.
4. Verify rewrite worker control:
   - keep UI control for `Rewrite workers`;
   - confirm `currentRewriteConfig()` sends `parallel_workers`;
   - confirm collect/rewrite/run-all endpoints pass `parallel_workers` into `GeminiRewriter`;
   - add manifest/log assertion that actual rewrite `parallel_workers` equals the requested value clamped by available chapter count and backend max;
   - if browser bridge/Gemini ports are the limiting factor, cap default to the ready browser pool size.
5. Verify TTS IO worker control:
   - keep UI control for `TTS IO workers (save/postprocess)`;
   - confirm run audio and run-all payloads pass `tts_io_workers`;
   - confirm `AudioPipelineService` sends `io_workers` to the TTS worker;
   - confirm worker logs/manifest expose effective `io_workers`;
   - align UI max with backend max, currently `6`, unless benchmark proves a different safe max.
6. Set fastest stable defaults by benchmark:
   - benchmark rewrite workers from `1..9` or up to ready browser pool count;
   - benchmark TTS IO workers from `1..6`;
   - choose the largest stable value that improves throughput without causing browser bridge failures, GPU starvation, disk contention, or memory pressure;
   - update frontend defaults and backend request defaults to those measured values;
   - document the chosen defaults with benchmark numbers.

Acceptance criteria:

- User can adjust chunk minimum words on frontend, but effective value cannot go below 30.
- Default seconds per image is 30 and is visible/effective in video payloads and manifests.
- Chunk output follows period-only/no-comma policy.
- User can adjust rewrite workers and the value affects actual rewrite concurrency.
- User can adjust TTS IO workers and the value affects worker save/postprocess concurrency.
- Defaults are the fastest stable values proven on the current RTX 3060/Windows setup, not just existing small defaults.
- UI max values and backend clamp values match.

Expected output:

- Frontend controls are trustworthy knobs for production speed.
- Worker manifests/logs prove the selected values were actually used.

## Phase 7: Candidate C/D escalation if needed (estimated 1-3 days)

Escalate only after Candidate B benchmark results are known.

If using FFmpeg GPU filters:

1. Add a probe command in the benchmark tool.
2. Build a GPU filter proof of concept for one scene.
3. Compare against Candidate B with the same source scene.
4. Reject if quality changes, unsupported filters require fragile local setup, or GPU upload/download loses speed.

If using a native GPU renderer:

1. Create an isolated prototype directory:
   - `spam_audio_video/renderers/native_gpu/`
2. Start with one-scene render only:
   - no audio;
   - no transition;
   - exact background/foreground/logo composition.
3. Add deterministic motion math copied from current pipeline.
4. Pipe to FFmpeg/NVENC or integrate NVENC SDK only after raw frame generation benchmark passes.
5. Add VFX and audio visualizer only after base visual parity is proven.

Acceptance criteria:

- At least 2x faster than Candidate B on the same 4K60 benchmark, or not worth replacing stable Python/FFmpeg pipeline.
- Same output metadata and no visible style drift.
- Build/run instructions are documented.

Expected output:

- Either a justified native/GPU renderer path or a documented rejection.

## Phase 8: Verification matrix (estimated 3 hours)

Required checks after each implementation phase:

1. Compile/static checks:
   - Python compile for changed backend/render modules.
   - Any native renderer build check if applicable.
2. Benchmark checks:
   - current baseline;
   - new renderer short benchmark;
   - current vs new comparison summary.
3. Metadata checks:
   - ffprobe width/height/fps/codec/pix_fmt;
   - audio stream codec/sample rate/channels;
   - duration and frame count tolerance.
4. Quality checks:
   - selected frame export from old/new renders;
   - SSIM/PSNR comparison;
   - manual spot check of motion, side padding, logo, visualizer, and VFX.
5. Runtime checks:
   - no `libx264`;
   - `h264_nvenc` selected;
   - no CPU fallback;
   - clear failure when GPU encoder is unavailable.
6. Frontend/control checks:
   - default seconds per image is 30 in frontend payloads and backend manifests;
   - chunk min words cannot go below 30 in UI or backend;
   - chunking uses period-only natural boundaries;
   - comma does not create a chunk boundary;
   - rewrite worker UI value is reflected in rewrite manifest/logs;
   - TTS IO worker UI value is reflected in audio manifest/logs;
   - selected defaults match benchmarked fastest stable values.
7. Browser bridge checks:
   - Gemini selected ports are pinged/warmed before Gemini rewrite/prompt phases;
   - GPT selected ports are pinged/warmed before GPT image phase;
   - Gemini and GPT used ports match their provider-specific selected lists;
   - GPT image text-only/no-asset responses return clear failures and trigger retry/failover.

Expected output:

- A benchmark-backed result showing whether the new renderer is faster and still equivalent.

## Phase 9: Documentation, logs, and rollout (estimated 1-2 hours)

1. Add documentation:
   - architecture decision;
   - benchmark commands;
   - result interpretation;
   - renderer selection;
   - troubleshooting.
2. Add implementation log:
   - phase-by-phase work;
   - benchmark numbers;
   - rejected options and why.
3. Update README only if the production workflow or benchmark command should be user-visible.
4. Keep old renderer during first rollout:
   - default to new renderer only after benchmark passes;
   - keep rollback env/config for one release cycle.
5. Review changed files.
6. Commit and push after all tests, docs, and logs pass.

Expected output:

- The project has a measurable faster render path, documented benchmark results, and a safe rollback route.

## Benchmark success targets

Minimum target:

- New renderer is at least 1.5x faster than current renderer on 4K60 short benchmark.
- No visible style change.
- No audio model/voice quality change. The only accepted audio text behavior change is the intentional period-only/no-comma chunk policy with effective minimum chunk words >= 30.

Strong target:

- New renderer is 2x-3x faster on 4K60 short benchmark.
- CPU usage drops meaningfully because static filters are not repeated per frame.
- NVENC remains active and GPU encoder utilization is stable.

Native/GPU rewrite target:

- Only worth replacing the FFmpeg precompute renderer if it is at least 2x faster than Candidate B, not just faster than the original baseline.

## Risk management

- Risk: precomputed still layers alter subtle filter output.
  - Mitigation: use the exact same FFmpeg filters, only move static filters earlier; compare frames.
- Risk: cache produces stale visuals.
  - Mitigation: cache key includes source hash, dimensions, filter settings, motion settings, and code renderer version.
- Risk: FFmpeg GPU filters differ across machines.
  - Mitigation: probe support and keep candidate optional until proven stable.
- Risk: native renderer grows too large.
  - Mitigation: require a one-scene proof of speed and visual parity before full integration.
- Risk: benchmark is too slow for daily use.
  - Mitigation: provide short and production benchmark modes.
- Risk: Gemini and GPT accidentally share ports through legacy `cdp_urls`.
  - Mitigation: add provider-specific config fields, explicit fallback rules, and manifest logging for selected/used ports.
- Risk: bridge ping semantics differ from pipeline expectations.
  - Mitigation: verify `toll-brouser-gpt-gemini` `/v1/ports/ping` behavior first; if it only probes, implement provider-aware warmup/open behavior in the bridge repo and test it there.
- Risk: GPT returns text instead of an image.
  - Mitigation: classify text-only/no-asset responses as failures in the bridge image endpoint and preserve retry/failover across selected GPT ports.

## Proposed implementation order

1. Add benchmark harness and current baseline.
2. Split Gemini/GPT browser ports and add provider warmup/ping behavior.
3. Implement precomputed layer renderer.
4. Benchmark and compare.
5. Optimize transition/overlay passes only where measurable.
6. Implement TTS period-only chunking and min_words >= 30.
7. Set seconds per image default to 30.
8. Wire frontend chunk/worker controls and benchmark fastest stable defaults.
9. Audit TTS for non-quality speed gains.
10. Escalate to FFmpeg GPU filters or native GPU renderer only if benchmark data justifies it.

## Implementation checkpoint 2026-05-16

- Implemented TTS period-only/no-comma policy with effective `min_words >= 30`.
- Implemented frontend defaults: TTS IO workers `6`, rewrite workers `9`, chunk min `30`, seconds per image `30`.
- Implemented provider-specific Gemini/GPT bridge port payloads and warmup/ping before provider phases.
- Implemented bridge failure classification for GPT text-only image responses.
- Added benchmark harness: `spam_audio_video/tools/benchmark_4k60_render.py`.
- Added bundled ffmpeg resolver and removed redundant single-clip re-encode before visual overlays.
- Real benchmark on `test-1/session_ch0001_to_ch0010`, 1 scene, 30s, 4K60:
  - Before single-clip optimization: 129.244s, speed 0.2321x.
  - After single-clip optimization: 102.707s, speed 0.2921x.
  - Encoder: `h264_nvenc`, `gpu_fallback_used=false`.
  - Output report: `spam_audio_video/projects_workspace/projects/test-1/sessions/session_ch0001_to_ch0010/video/renders/benchmark_4k60_smoke4.benchmark.json`.
- The 1.5x minimum speed target is not yet reached; next optimization should be true precomputed foreground/background layers or fusing final visual overlays into render graphs where scene transitions allow it.

## Benchmark artifact and cleanup rule

All future render benchmark work must write evidence into a dedicated benchmark folder instead of leaving reports, screenshots, frame dumps, or videos scattered across source folders.

Recommended root:

```text
spam_audio_video/benchmarks/render_4k60/
```

Each run should create a timestamped folder with:

- `input/`: renderer input JSON and source manifest;
- `output/`: baseline video, candidate video, final muxed video when applicable;
- `reports/`: `benchmark.json`, `quality.json`, `summary.md`, ffprobe reports, renderer report;
- `frames/`: extracted baseline/candidate/diff frames;
- `screenshots/`: UI or visual-inspection screenshots;
- `logs/`: stdout/stderr, GPU/NVENC samples, `nvidia-smi` snapshot when available.

After every implementation phase:

- remove unused imports, dead code, debug prints, and abandoned prototype files;
- keep generated videos/images/reports only under benchmark/runtime artifact folders;
- run targeted compile/test checks for touched files;
- update the plan/log with benchmark folder paths and cleanup decisions.
