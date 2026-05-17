# Runtime Test Report: Video Pipeline

Date: 2026-05-03

Status: historical report. Current production video rendering is the
Rust/D3D11/NVENC story timeline path documented in
`docs/release_notes_v0.1.6.md`; legacy silent/final filenames are no longer
the current release contract.

## Scope

Validate the new session-first video pipeline runtime from API layer through generated artifacts.

Tested session:
- `project_id=test-1`
- `session_id=session_ch0001_to_ch0050`

## Test Matrix

1. Python compile validation
- Command:
  - `python -m py_compile auto_generate_video/pipeline.py source_full/backend/video_service.py source_full/backend/server.py source_full/backend/pipeline_service.py auto_convert_text/storage/project_store.py`
- Result: PASS

2. Video prewarm API
- Endpoint: `POST /api/pipeline/video/prewarm`
- Payload: `project_id=test-1`, `session_id=session_ch0001_to_ch0050`
- Result: PASS (API healthy), runtime not fully configured for SD model
- Assertions:
  - HTTP 200
  - `result.ffmpeg_ok=True`
  - `result.ok=False` when SD executable/model path are not configured

3. Video analyze API
- Endpoint: `POST /api/pipeline/video/analyze`
- Payload: `scene_duration_seconds=60`
- Result: PASS
- Assertions:
  - HTTP 200
  - `scene_count=5`
  - `total_audio_seconds=263.47`
  - analysis manifest created at:
    - `projects_workspace/projects/test-1/sessions/session_ch0001_to_ch0050/video/manifests/analysis_manifest.json`

4. Video prompts API (fake provider)
- Endpoint: `POST /api/pipeline/video/prompts`
- Payload: `provider=fake`
- Result: PASS
- Assertions:
  - HTTP 200
  - prompt files created under session `video/prompts/`
  - prompts manifest created

5. Video images API (fake provider, placeholder fallback)
- Endpoint: `POST /api/pipeline/video/images`
- Payload: `provider=fake`
- Result: PASS
- Assertions:
  - HTTP 200
  - image files created under session `video/images/`
  - image manifest reports `engine=placeholder`

6. Video render API
- Endpoint: `POST /api/pipeline/video/render`
- Result: PASS
- Assertions:
  - HTTP 200
  - render path followed the old contract.
  - current contract uses `story_render*.mp4`

7. Video merge API
- Endpoint: `POST /api/pipeline/video/merge`
- Result: PASS
- Assertions:
  - HTTP 200
  - final path followed the old contract.
  - current contract uses `story_render*_with_audio.mp4`

8. Full video run API
- Endpoint: `POST /api/pipeline/video/run`
- Payload: fake provider + merge_audio=true
- Result: PASS
- Assertions:
  - HTTP 200
  - all stages completed in one call
  - session outputs remain available for frontend list/download

9. Real endpoint prompt smoke
- Endpoint: `POST /api/pipeline/video/prompts`
- Payload: `provider=openai_compat`, `llm_base_url=http://localhost:20128/v1`
- Result: PASS
- Assertions:
  - HTTP 200
  - `scene_count=5`
  - scene prompt files updated successfully under session `video/prompts/`
  - prompts manifest stores `llm_base_url` + `llm_model` for traceability

## Runtime Notes

- The pipeline now supports fallback duration/merge behavior when `audio/combined.wav` is missing:
  - duration is computed from per-file `audio/text_*.wav`
  - merge can auto-build a temporary combined wav inside `video/renders/auto_combined.wav`
- Production SD image generation requires:
  - `VIDEO_SD_EXECUTABLE`
  - `VIDEO_SD_MODEL_PATH`
- Fake provider mode keeps end-to-end smoke testable before SD runtime is fully configured.

## Conclusion

Video pipeline runtime is operational and testable end-to-end in session-first mode.

Pass summary:
- API contract: PASS
- Session artifact contract: PASS
- End-to-end run (fake provider): PASS
- Download-ready outputs at session video root: PASS
