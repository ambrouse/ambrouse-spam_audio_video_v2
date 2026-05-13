# Plan: render video VFX and audio visualizer

Date: 2026-05-13

## Goal

Improve the current video render pipeline without disturbing the parts that are already working well:

- Keep the existing vertical scroll animation, side padding, background fill, and logo placement.
- Replace the weak VFX layer with a more intentional cinematic overlay: chalk-dust drift plus light spark streaks.
- Add an audio-reactive visualizer bar that uses colors sampled from the generated scene image palette.
- Keep the effect subtle enough for story review videos: no heavy center obstruction, no large text, no layout shift.
- Verify with compile/runtime-safe checks, then document, log, commit, and push.

## Skills used

- `project-workflow`: follow repository-specific workflow.
- `plan-skill`: create this task plan before implementation.
- `backend-skill`: update Python render pipeline cleanly.
- `frontend-skill`: inspect UI/API payloads and avoid breaking current controls.
- `documentation-skill`: write final task documentation in root `docs/`.
- `logging-skill`: write concise work log in root `logs/`.
- `push-code-skill`: verify, commit with clear timestamp, and push to GitHub.

## Phase 1: Source and doc review (estimated 25 minutes)

1. Read root README, `spam_audio_video/README.md`, existing root docs/logs/plans, and video pipeline test docs.
2. Inspect `spam_audio_video/auto_generate_video/pipeline.py`, backend video service/API models, and frontend payload builders.
3. Confirm existing render behavior: scene image sequence, vertical-only scroll, side padding, logo overlay, audio mux.

Expected output:

- Clear implementation surface: `auto_generate_video/pipeline.py` owns the render VFX layer.

## Phase 2: Plan and VFX design (estimated 15 minutes)

1. Preserve current scroll/padding/logo.
2. Use image palette sampling instead of fixed dust tint.
3. Build two particle layers:
   - chalk dust: soft, slow, low-alpha, broad drift.
   - sparks: fewer warm/palette-colored vertical streaks near lower/safe areas.
4. Add audio visualizer only when audio can be resolved, using FFmpeg audio filters.
5. Keep all generated overlay information in `render_manifest.json` for traceability.

Expected output:

- VFX design is implemented as backend render defaults, so existing UI/API calls automatically benefit.

## Phase 3: Implementation (estimated 45 minutes)

1. Extend visual overlay call to resolve session audio before final mux.
2. Replace average-only dust color logic with palette statistics from the reference image.
3. Add helper methods for palette hex conversion and particle filter construction.
4. Add audio visualizer filter chain with graceful fallback when audio is unavailable.
5. Update progress message and manifest fields to describe palette VFX and visualizer.

Expected output:

- Rendered videos include harmonious palette-based particles and audio-reactive bar.

## Phase 4: Verification (estimated 35 minutes)

1. Run Python compile checks for changed backend/render modules.
2. Run focused helper/runtime checks for palette sampling and overlay filter creation.
3. If practical, run a small FFmpeg smoke render using existing session/image/audio artifacts.
4. Check `git diff` to ensure only intended files were touched.

Expected output:

- Compile passes.
- Overlay helper path is exercised without requiring full production image generation.

## Phase 5: Documentation, log, push (estimated 25 minutes)

1. Add root documentation summarizing the VFX/render change and verification.
2. Add root log with the concise implementation timeline.
3. Review changed files.
4. Commit with timestamped message.
5. Push `main` to GitHub.

Expected output:

- Task is documented, logged, committed, and pushed.
