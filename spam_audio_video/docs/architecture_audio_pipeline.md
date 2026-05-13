# Audio Pipeline Architecture (Current Scope)

## Goal
Current implementation focuses on `auto_text_to_voice` stage in the full future pipeline:
1. `auto_convert_text`
2. `auto_text_to_voice` (implemented now)
3. `auto_generate_video`

## Components
- `source_full/backend/server.py`
  - FastAPI entrypoint.
  - Exposes `POST /api/pipeline/audio/run`.
  - Uses in-process lock to prevent duplicate run collisions.
- `source_full/backend/pipeline_service.py`
  - Uses persistent worker IPC (`auto_text_to_voice/vieneu_worker.py`).
  - Sends synth payload and receives structured JSON reply/manifest.
- `auto_text_to_voice/vieneu_worker.py`
  - Loads `.txt` from active session `projects_workspace/projects/<project_id>/sessions/<session_id>/tts_inputs/`.
  - Uses one voice reference audio + transcript from `auto_text_to_voice/voice`.
  - Generates one `.wav` per `.txt` into session audio folder.
  - Merges all generated wav files into session `combined.wav`.
  - Writes session `manifest.json`.
  - Supports TTS IO parallel stage (`io_workers`) for write/postprocess overlap while keeping synth/model path stable.
- `source_full/frontend/*`
  - Single-page controller UI with run button and loading bar.

## Video Pipeline (Session-first, current)

- `auto_generate_video/pipeline.py`
  - Computes scene count from session audio duration and configurable seconds-per-image.
  - Groups `tts_inputs/*.txt` into scene buckets.
  - Generates scene prompts (fake or Gemini web).
  - Generates scene images (SD GGUF local runtime, fake-mode placeholder fallback for smoke test).
  - Renders subtle camera-motion silent video.
  - Merges session audio into final video output.

- `source_full/backend/video_service.py`
  - Service orchestration and shared registry updates for video stages.

- `source_full/backend/server.py`
  - Exposes video APIs:
    - `POST /api/pipeline/video/prewarm`
    - `POST /api/pipeline/video/analyze`
    - `POST /api/pipeline/video/prompts`
    - `POST /api/pipeline/video/images`
    - `POST /api/pipeline/video/render`
    - `POST /api/pipeline/video/merge`
    - `POST /api/pipeline/video/run`

- `projects_workspace/projects/<project_id>/sessions/<session_id>/video/`
  - `prompts/`, `images/`, `renders/`, `final/`, `manifests/`
  - Root keeps downloadable outputs: `story_silent.mp4`, `final_story.mp4`

## Extension direction
- Keep API contract stable and add staged endpoints:
  - `/api/pipeline/convert/run`
  - `/api/pipeline/audio/run`
  - `/api/pipeline/video/run` (implemented)
- Later move heavy jobs to queue workers (Redis/RabbitMQ) while keeping same orchestration contract.
