# Render video VFX and audio visualizer - 2026-05-13

## Scope

Improved the `spam_audio_video` render stage while preserving the current video foundation:

- Kept existing scene scroll, side padding, blurred background fill, and logo overlay.
- Replaced the older single dust tint with palette-aware cinematic VFX.
- Added two subtle particle layers:
  - chalk-dust drift for soft ambience.
  - spark streaks for light motion accents.
- Added an audio-reactive frequency bar when session audio is available.
- Stored palette/VFX metadata in `video/manifests/render_manifest.json`.

## Design Notes

The VFX color selection now samples a small RGB grid from the first render image:

- `average_rgb` controls light/dark dust behavior.
- `dominant_rgb` records the most common image bucket.
- `accent_rgb` drives spark and visualizer color after softening against the average image tone.

This keeps the bar and particles closer to the generated art instead of using a fixed purple/gray overlay for every scene.

The visualizer is intentionally placed near the lower safe area and rendered with transparency so it feels like part of the video, not a separate UI panel. If audio cannot be resolved, render still succeeds with palette particles and logo.

## Changed Files

- `spam_audio_video/auto_generate_video/pipeline.py`
  - Resolves session audio before the final audio mux so the render overlay can use it as a visualizer source.
  - Adds palette sampling helpers.
  - Adds palette-based dust and spark particle filter generation.
  - Adds FFmpeg `showfreqs` audio bar overlay with graceful fallback.
  - Extends render manifest overlay fields.

## Verification

- Passed Python compile:
  - `python -m py_compile auto_generate_video/pipeline.py source_full/backend/video_service.py source_full/backend/server.py`
- Passed helper smoke check:
  - palette sampling
  - VFX palette selection
  - particle filter construction
- Passed FFmpeg smoke render:
  - generated a short base MP4 from an existing scene image
  - generated a short WAV tone
  - applied the real `_apply_visual_overlays(...)` path with logo and audio visualizer
  - output MP4 was produced successfully

## Runtime Impact

Existing UI/API calls do not need new payload fields. The VFX upgrade is applied by default during `/api/pipeline/video/render` and full video runs.
