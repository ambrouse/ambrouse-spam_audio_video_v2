# Plan: native GPU 4K60 renderer target 8x-12x

Date: 2026-05-16

## Goal

Build a new high-performance video renderer path that can realistically target **8x-12x faster** than the current FFmpeg multi-pass renderer while preserving the same production output contract.

Current measured checkpoint:

- Current optimized FFmpeg path: `30s` 4K60 scene renders in `102.707s`.
- Current speed: `0.2921x`.
- 8x target means `30s` scene should render in about `12.84s` or less.
- 12x target means `30s` scene should render in about `8.56s` or less.

Non-negotiable output contract:

- Final video stays exactly `3840x2160`, `60fps`, H.264 hardware encoded.
- Encoder must remain hardware, preferably `h264_nvenc`; no silent CPU fallback.
- Audio output, TTS model, TTS voice, and mux behavior must not change.
- Visual style must remain equivalent:
  - same background/foreground composition intent;
  - same scroll/zoom/motion rhythm;
  - same logo placement;
  - same particles/VFX intent;
  - same audio visualizer behavior when enabled;
  - same output duration policy.
- Any renderer that cannot prove quality parity and benchmark gain must stay experimental.

Important expectation:

- **8x-12x is not realistic with small FFmpeg tweaks.**
- The best path is a **native GPU renderer** that renders the full timeline in one GPU pass and encodes once.
- Python should remain the orchestration layer, not the frame-generation layer.

## Required skills

- `plan-skill`: maintain this plan and execute phase by phase.
- `project-workflow`: keep repo conventions, docs, logs, and review flow aligned.
- `backend-skill`: integrate renderer selection, manifests, benchmark endpoints, and failure handling.
- `frontend-skill`: expose renderer/benchmark controls only after the renderer is proven stable.
- `testing-skill`: if unavailable locally, use repo-local tests, benchmark scripts, ffprobe, SSIM/VMAF/pixel-diff, and real pipeline smoke renders.
- `documentation-skill`: document architecture, build instructions, quality gates, benchmark interpretation, and rollback.
- `logging-skill`: log each phase and benchmark result.
- `push-code-skill`: only push after benchmark, docs, logs, and review pass.

## Architecture decision

Primary candidate:

- **Rust + wgpu + NVENC/FFmpeg pipe**

Why this first:

- Rust gives safer native code than C++ for a large renderer.
- `wgpu` gives DirectX 12/Vulkan/Metal abstraction, with Windows GPU acceleration through native backends.
- Rendering math can move from FFmpeg filters into GPU shaders.
- Encoding can initially use FFmpeg `h264_nvenc` through a raw frame pipe to reduce implementation risk.
- If the raw-frame pipe becomes a bottleneck, Phase 7 can replace it with NVIDIA Video Codec SDK direct NVENC.

Fallback candidate for maximum performance only after proof:

- **C++ + Direct3D 11/12 + NVIDIA Video Codec SDK**

Why not start here:

- Higher build complexity.
- More memory/lifetime risk.
- More time before first useful benchmark.
- Only worth it if Rust/wgpu cannot reach 8x and profiling proves raw-frame transfer or wgpu overhead is the bottleneck.

## Target folder structure

New code must be isolated and clean:

```text
spam_audio_video/
  native_renderers/
    story_gpu_renderer/
      Cargo.toml
      README.md
      src/
        main.rs
        cli.rs
        config.rs
        timeline.rs
        assets.rs
        renderer/
          mod.rs
          device.rs
          shaders.rs
          frame_graph.rs
          motion.rs
          particles.rs
          overlays.rs
        encoder/
          mod.rs
          ffmpeg_pipe.rs
          nvenc_sdk.rs          # only after Phase 7 if justified
        quality/
          mod.rs
          frame_dump.rs
      shaders/
        composite.wgsl
        blur.wgsl
        sharpen.wgsl
        particles.wgsl
        visualizer.wgsl
      benches/
        sample_timeline.json
      tests/
        timeline_parse.rs
        motion_math.rs
  benchmarks/
    native_gpu_4k60/
      README.md
      {timestamp}_{renderer}_{scenario}/
        input/
          renderer_input.json
          source_manifest.json
        output/
          current_ffmpeg.mp4
          native_gpu.mp4
          native_gpu_with_audio.mp4
        reports/
          benchmark.json
          quality.json
          summary.md
          ffprobe_current.json
          ffprobe_native.json
          renderer_report.json
        frames/
          current/
          native/
          diff/
        screenshots/
          desktop_preview.png
          metadata_preview.png
        logs/
          stdout.log
          stderr.log
          gpu_samples.csv
          nvidia_smi.txt
  tools/
    benchmark_4k60_render.py
    compare_render_quality.py
  auto_generate_video/
    pipeline.py
```

Integration code remains thin:

- Python pipeline creates a renderer input JSON.
- Native renderer outputs `.mp4` and a renderer report JSON.
- Python validates output metadata and records it in `render_manifest.json`.

## Benchmark artifact policy

All benchmark evidence must be stored in a dedicated benchmark folder, not scattered through production session folders.

Primary benchmark root:

```text
spam_audio_video/benchmarks/native_gpu_4k60/
```

Each benchmark run must create one immutable timestamped folder:

```text
spam_audio_video/benchmarks/native_gpu_4k60/{YYYYMMDD_HHMMSS}_{renderer}_{scenario}/
```

Required contents:

- `input/renderer_input.json`: exact renderer input used for the run.
- `input/source_manifest.json`: source images/audio/session metadata.
- `output/current_ffmpeg.mp4`: baseline output when a comparison run is requested.
- `output/native_gpu.mp4`: native output without audio when render-only benchmark is used.
- `output/native_gpu_with_audio.mp4`: final muxed output when audio benchmark is used.
- `reports/benchmark.json`: wall time, speed multiplier, per-stage timings, CPU/GPU/NVENC samples, pass/fail.
- `reports/quality.json`: SSIM/PSNR/frame-diff/audio metadata checks.
- `reports/summary.md`: human-readable benchmark conclusion.
- `reports/ffprobe_*.json`: ffprobe metadata for every compared video.
- `reports/renderer_report.json`: native renderer internal timings and device info.
- `frames/current/`: extracted baseline frames.
- `frames/native/`: extracted native frames.
- `frames/diff/`: diff images for failed or sampled frame comparisons.
- `screenshots/`: UI, preview, or metadata screenshots when frontend or visual inspection is part of the test.
- `logs/stdout.log` and `logs/stderr.log`: complete renderer and FFmpeg logs.
- `logs/gpu_samples.csv` and `logs/nvidia_smi.txt`: GPU/NVENC telemetry when available.

Rules:

- Benchmark folders are append-only evidence. Do not overwrite an old run.
- Heavy video artifacts may be ignored by Git later, but the plan/log must keep the folder path and summary.
- A benchmark is not considered valid unless `benchmark.json`, `quality.json`, `summary.md`, and the output video exist.
- Production session folders may receive final outputs, but benchmark evidence must also be copied into the benchmark folder.

## Effective patterns to use

Use these patterns deliberately:

- **One-pass timeline renderer**
  - Render each final frame once.
  - Avoid `clip encode -> concat encode -> overlay encode`.
  - Compose scene, transition, particles, logo, and optional visualizer before encode.

- **Data-oriented frame graph**
  - Precompute timeline constants once.
  - Per frame, upload only frame index/time and small uniform buffers.
  - Assets stay resident on GPU.

- **Texture cache**
  - Decode source images once per scene.
  - Keep background, foreground, logo, particle buffers, and LUT-like constants cached.
  - Cache key includes source image hash, dimensions, renderer version, style config, and shader version.

- **Shader parity layer**
  - Implement existing FFmpeg effects as named shader stages:
    - background scale/crop/blur/equivalent saturation/brightness;
    - foreground scale/sharpen/equivalent panel crop;
    - pan/scroll/zoom;
    - particles;
    - logo overlay;
    - audio visualizer if enabled.
  - Every shader stage has a matching quality test or frame-diff checkpoint.

- **Zero-copy ambition, staged adoption**
  - Phase 1 uses FFmpeg pipe for encode to reduce risk.
  - Phase 7 profiles whether CPU readback/raw pipe is the bottleneck.
  - Only then add direct NVENC SDK.

- **Fail-loud production gate**
  - No CPU fallback.
  - If native renderer is unavailable or quality gate fails, production does not silently switch.
  - User must explicitly choose experimental renderer until benchmark target passes.

## Phase 0: protect current working state (estimated 30 minutes)

1. Record current dirty worktree state.
2. Identify unrelated user changes and do not revert them.
3. Confirm current benchmark artifacts:
   - `benchmark_4k60_smoke4.mp4`
   - `benchmark_4k60_smoke4.benchmark.json`
4. Add a clean benchmark baseline JSON under runtime benchmarks if not already present.

Acceptance:

- Current FFmpeg production path remains runnable.
- Baseline number is recorded: `30s / 102.707s / h264_nvenc / no fallback`.

## Phase 1: quality contract and golden fixture (estimated 4-6 hours)

1. Create golden render fixture from an existing real session:
   - project: `test-1`
   - session: `session_ch0001_to_ch0010`
   - scene count: 1, 2, and 5 modes.
2. Write quality tool:
   - `spam_audio_video/tools/compare_render_quality.py`
3. Quality checks:
   - ffprobe metadata equality:
     - width `3840`;
     - height `2160`;
     - fps `60`;
     - H.264 hardware encoded;
     - duration delta <= one frame for render-only comparisons.
   - selected-frame comparison:
     - frame at 0%, 10%, 25%, 50%, 75%, 90%, 100%-1 frame;
     - SSIM >= `0.995` for stages expected to match closely;
     - PSNR target >= `42dB`;
     - if shader math cannot match FFmpeg exactly, require visual diff report and approval gate.
   - audio:
     - render-only changes must keep audio stream metadata and hash unchanged after mux.
4. Store reports:
   - `projects_workspace/runtime/benchmarks/render_4k60/{timestamp}/quality.json`
   - `summary.md`

Acceptance:

- Quality tool can compare current renderer output against itself and pass.
- The tool fails clearly when dimensions/fps/encoder/duration are wrong.

## Phase 2: renderer input contract (estimated 3-5 hours)

1. Add renderer input JSON schema:
   - session paths;
   - image list;
   - audio path;
   - output path;
   - width/height/fps;
   - seconds per image;
   - motion config;
   - visual overlay config;
   - encoder config;
   - deterministic seed.
2. Add Python exporter in `auto_generate_video/pipeline.py`:
   - build exact native renderer input from current render plan;
   - no rendering yet.
3. Add JSON validation test:
   - missing image fails;
   - invalid resolution fails;
   - CPU encoder request fails;
   - deterministic seed stable for same project/session.

Acceptance:

- Native renderer input JSON fully describes a render without needing hidden Python state.
- Existing FFmpeg renderer still works unchanged.

## Phase 3: Rust/wgpu proof-of-speed renderer MVP (estimated 2-4 days)

Goal:

- Render a visually simplified but structurally correct 4K60 timeline fast enough to prove the architecture.

Implementation:

1. Create Rust crate under `spam_audio_video/native_renderers/story_gpu_renderer`.
2. CLI:
   - `story_gpu_renderer render --config input.json --report report.json`
3. Implement:
   - load images;
   - create GPU textures;
   - render 4K frames with foreground/background composition;
   - apply pan/scroll/zoom motion;
   - pipe raw frames to FFmpeg `h264_nvenc`;
   - write renderer report JSON with per-stage timings.
4. Keep visual effects minimal in this phase:
   - no particles yet;
   - no audio visualizer yet;
   - optional logo only if cheap.

Acceptance:

- Produces valid `3840x2160@60` H.264 output.
- No CPU encoder fallback.
- 30s / 1 scene benchmark <= `20s`.
- If MVP cannot reach <= `20s`, profile before adding style complexity.

Decision gate:

- If MVP is slower than `20s`, do not continue blindly.
- Profile:
  - image decode;
  - GPU render;
  - readback;
  - FFmpeg pipe;
  - NVENC utilization.
- If bottleneck is raw frame pipe/readback, escalate direct NVENC earlier.

## Phase 4: visual parity shader implementation (estimated 4-8 days)

Implement current style stage by stage.

1. Background:
   - cover-scale/crop;
   - blur approximation;
   - saturation/brightness adjustment.
2. Foreground:
   - panel sizing;
   - scroll crop;
   - zoom;
   - sharpen approximation.
3. Transition:
   - dissolve/xfade equivalent.
4. Logo:
   - exact placement and alpha behavior.
5. Particles:
   - deterministic dust/spark generation;
   - seed matches current manifest behavior;
   - same count/range/intensity intent.
6. Audio visualizer:
   - precompute audio spectrum/level texture or CPU-side compact buffer;
   - render bars in shader.

Testing pattern:

- After each stage:
  - render 5-second sample;
  - compare metadata;
  - compare selected frames;
  - save diff images if quality gate fails.

Acceptance:

- Full native output passes quality gate against current renderer.
- Any intentional non-bit-exact differences are documented and approved before production use.

## Phase 5: Python backend integration (estimated 1-2 days)

1. Add renderer selection:
   - `renderer=current_ffmpeg|native_gpu_experimental`
   - default remains current until target passes.
2. Add native renderer discovery:
   - find binary;
   - validate version;
   - validate GPU backend;
   - validate FFmpeg/NVENC or direct NVENC availability.
3. Add run path:
   - export native renderer input JSON;
   - run native binary;
   - validate output via ffprobe;
   - merge report into `render_manifest.json`.
4. Failure behavior:
   - no fallback unless user explicitly reruns current renderer;
   - clear error message with stage timing and stderr.

Acceptance:

- Existing video endpoints can run native renderer experimentally.
- Existing current FFmpeg renderer remains available and unchanged.

## Phase 6: benchmark target gate 8x-12x (estimated 1-2 days)

Benchmark matrix:

1. One-scene smoke:
   - 1 scene x 30s x 4K60.
2. Multi-scene transition:
   - 5 scenes x 30s x 4K60.
3. Production-like:
   - all available session images x 30s x 4K60.

Required metrics:

- wall time;
- render speed multiplier versus `102.707s` one-scene baseline;
- GPU usage;
- NVENC usage;
- CPU usage;
- peak memory;
- output metadata;
- quality score.

Pass target:

- Minimum acceptable for this task: **8x** on one-scene smoke:
  - <= `12.84s` for 30s output.
- Strong target: **12x** on one-scene smoke:
  - <= `8.56s` for 30s output.
- Multi-scene target:
  - >= `6x` if transitions/audio visualizer add overhead.
- No quality gate failure.

Acceptance:

- If native renderer reaches >= `8x`, it can be considered for production default behind an explicit config gate.
- If it reaches `3x-7.9x`, keep it experimental and continue Phase 7 optimization.
- If it stays below `3x`, document why and stop native path unless profiling shows a clear fix.

## Phase 7: direct NVENC escalation if needed (estimated 4-10 days)

Only start this if Phase 6 shows raw frame pipe/readback is the main bottleneck.

Options:

1. Rust FFI to NVIDIA Video Codec SDK.
2. C++ encoder helper process using NVIDIA Video Codec SDK.
3. Full C++ Direct3D + NVENC renderer if Rust/wgpu interop blocks zero-copy.

Target:

- avoid CPU readback;
- keep GPU texture path into NVENC;
- reduce encode overhead enough to reach 8x-12x.

Acceptance:

- Direct NVENC path beats FFmpeg pipe by at least `1.5x`.
- It does not reduce quality or change metadata.
- Build instructions are reproducible on Windows.

## Phase 8: cleanup and deprecation (estimated 1 day)

Clean only after native path proves useful.

1. Remove unused experimental files.
2. Delete dead helper functions superseded by renderer input schema.
3. Keep current FFmpeg renderer as a rollback path for one release cycle.
4. Move old benchmark artifacts that are no longer useful into an archived runtime folder or document why they stay.
5. Ensure no duplicated render math exists without a test:
   - Python owns timeline/export;
   - native owns frame rendering;
   - benchmark owns validation.
6. Run a source cleanup checklist after every implementation phase:
   - remove unused imports, dead code, temporary debug prints, and abandoned prototype modules;
   - keep comments only where they explain non-obvious renderer math, GPU synchronization, encoder behavior, or quality gates;
   - move throwaway scripts into benchmark artifacts or delete them;
   - ensure new folders have a clear owner and README if they are not self-explanatory;
   - run formatter/linter/compile checks for touched Rust/Python/JS files;
   - confirm no generated videos, frame dumps, screenshots, or benchmark logs are accidentally placed in source folders.

Acceptance:

- No orphaned prototype scripts.
- No hidden renderer config outside documented JSON.
- Folder structure remains understandable.
- Source tree is clean after every phase; generated artifacts live under `spam_audio_video/benchmarks/native_gpu_4k60/` or runtime output folders only.

## Phase 9: frontend controls after proof (estimated 4-8 hours)

Only expose controls after Phase 6 passes.

1. Add renderer selector:
   - Current FFmpeg;
   - Native GPU experimental;
   - Native GPU production only after 8x target passes.
2. Add benchmark button or command hint.
3. Show renderer report:
   - speed multiplier;
   - encoder;
   - GPU fallback status;
   - quality gate status.

Acceptance:

- User can select native renderer intentionally.
- UI does not hide failed quality/benchmark status.

## Phase 10: documentation and logs (estimated 4-6 hours)

Documentation:

- `docs/native-gpu-renderer.md`
  - architecture;
  - build instructions;
  - renderer input schema;
  - benchmark commands;
  - quality gates;
  - troubleshooting.

Logs:

- `logs/spam_audio_video/{date}-native-gpu-renderer.md`
  - phase history;
  - benchmark results;
  - decisions;
  - failures and fixes.

README:

- Add only a short pointer after native renderer is runnable.

Acceptance:

- A new developer can build, benchmark, and validate native renderer from docs.

## Final acceptance checklist

- Native renderer builds reproducibly on Windows.
- Current FFmpeg renderer still works.
- Native renderer produces valid 4K60 H.264 hardware output.
- No CPU encoder fallback.
- Audio behavior unchanged.
- Visual quality gate passes.
- One-scene benchmark reaches at least 8x:
  - <= `12.84s` for 30s output against current `102.707s` baseline.
- Strong pass reaches 12x:
  - <= `8.56s` for 30s output.
- Multi-scene benchmark is documented.
- Every pass/fail benchmark has a timestamped artifact folder containing reports, screenshots/frame captures, videos, logs, and telemetry.
- Code is separated cleanly under `native_renderers/story_gpu_renderer`.
- Unused prototypes are removed.
- Source code is cleaned after implementation: no unused logic, no abandoned debug code, no generated artifacts in source folders.
- Plan, docs, logs, benchmark reports are updated.

## Implementation checkpoint 2026-05-16

Completed:

- Installed Rust toolchain and Visual Studio Build Tools C++ workload required for Rust MSVC builds.
- Added benchmark artifact roots:
  - `spam_audio_video/benchmarks/render_4k60/`
  - `spam_audio_video/benchmarks/native_gpu_4k60/`
- Updated `benchmark_4k60_render.py` to write timestamped artifact folders.
- Added `compare_render_quality.py` for metadata checks, frame extraction, SSIM, and PSNR reports.
- Added Python native renderer input exporter in `VideoPipeline.build_native_renderer_input(...)`.
- Scaffolded Rust crate:
  - `spam_audio_video/native_renderers/story_gpu_renderer/`
  - clean CLI/config/report/encoder modules;
  - cargo target output moved to `D:/cargo-target/story_gpu_renderer` so generated build files do not pollute source folders.

Benchmark evidence:

- Current FFmpeg artifact:
  - folder: `spam_audio_video/benchmarks/render_4k60/20260516_221957_current_ffmpeg_one_scene_30s/`
  - elapsed: `104.298s`
  - 4K60/NVENC metadata pass;
  - self quality pass: SSIM `1.0`, PSNR `inf`.
- Native speed-probe artifact:
  - folder: `spam_audio_video/benchmarks/native_gpu_4k60/20260516_223237_native_gpu_speed_probe_one_scene_30s/`
  - elapsed after clean rebuild: `25.835s`
  - multiplier vs baseline `102.707s`: `3.9755x`
  - 8x pass: `false`
  - 12x pass: `false`
  - quality pass: `false`, SSIM `0.609109`, PSNR `13.960153`

Decision:

- The FFmpeg/NVENC pipe speed ceiling is not enough for 8x-12x.
- Continuing with a pipe-based renderer cannot meet the stated target.
- Next implementation must move to **direct GPU texture-to-NVENC** or equivalent zero-copy encoder integration before full shader parity work.

## Risks

- Risk: shader output cannot visually match FFmpeg filters closely enough.
  - Mitigation: stage-by-stage parity tests and diff reports.
- Risk: raw frame pipe to FFmpeg blocks 8x-12x.
  - Mitigation: direct NVENC Phase 7.
- Risk: audio visualizer is expensive or hard to match.
  - Mitigation: precompute compact audio buffers and test separately.
- Risk: build toolchain becomes too complex.
  - Mitigation: Rust/wgpu first, C++ only if profiling justifies it.
- Risk: native renderer becomes a second untested render pipeline.
  - Mitigation: JSON schema, quality tool, benchmark gate, and explicit production switch only after pass.
