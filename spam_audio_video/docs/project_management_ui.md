# Project Management UI And Shared Registry

Date: 2026-04-29

## Goal

The web controller now manages story work by project instead of making each stage feel like a loose file operation.

Shared project state lives outside the pipeline folders:

```text
project_registry/projects.json
```

Both major pipelines update that registry:

```text
auto_convert_text -> project_registry/projects.json <- auto_text_to_voice
```

Each convert run is now a session:

```text
projects_workspace/projects/<project_id>/sessions/<session_id>/
  session.json
  chapters_manifest.json
  rewrite_manifest.json
  audio_clean_manifest.json
  chunks_manifest.json
  tts_export_manifest.json
  chapters_text/
    raw/
    rewritten/
    audio_clean/
    chunks/
  tts_inputs/
```

## Registry Contract

Each project record stores:

- `project_id`, `name`, `status`, `notes`
- source URL and chapter increment token
- convert metadata: raw count, rewrite count, chunk count, exported TTS text count
- TTS metadata: selected voice, model, manifest path, combined audio path, generated file count
- `sessions[]`, where each session stores chapter start/end, status, convert metadata, and TTS metadata

The convert artifacts now stay in per-session folders:

```text
projects_workspace/projects/<project_id>/sessions/<session_id>/
```

The TTS runtime reads session text directly from:

```text
projects_workspace/projects/<project_id>/sessions/<session_id>/tts_inputs/
```

The difference is that convert, TTS, and frontend now use the same project workspace for session data.

## UI Pages

- `Projects`: project list, session list, status metrics, active project/session selection, rename, notes, delete.
- `Convert`: run chapter crawl -> Gemini rewrite -> audio clean -> chunk -> TTS text export.
- `Voice`: run audio generation for the active project/session and update the shared registry.
- `Assets`: inspect/edit TTS text files inside the active session and preview/download audio/video outputs.

## Progress Contract

The loadscene no longer uses a fake timer as the source of truth.

The frontend sends a `job_id` to `POST /api/convert/run-full`, polls `GET /api/jobs/{job_id}`, and renders:

- current stage.
- current chapter/file message.
- files done.
- process units done/total.
- percent computed from real stage/file progress.

The visual bar still animates smoothly, but the value comes from backend progress callbacks.

## API

- `GET /api/projects`
- `GET /api/projects/{project_id}`
- `PUT /api/projects/{project_id}`
- `POST /api/projects/{project_id}/delete`
- `POST /api/projects/{project_id}/sessions/{session_id}/delete`
- `GET /api/jobs/{job_id}`
- `POST /api/pipeline/audio/run` accepts optional `project_id`
  and optional `session_id`

## Runtime Proof

- Fake Gemini full pipeline + shared project CRUD + frontend smoke: PASS.
- Real Gemini adapter smoke through Chrome remote debugging: PASS.
- Real Gemini full convert smoke with one local chapter: PASS.
- Session artifact runtime with chunk export and progress API: PASS.
- Live frontend sessions/progress smoke: PASS.
- Convert/session/chunk/clean runtime with Vietnamese consistency checks: PASS.
