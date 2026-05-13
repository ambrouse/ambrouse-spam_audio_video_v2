<p align="center">
  <img src="https://raw.githubusercontent.com/ambrouse/img/main/icon1.svg" alt="Project Logo" width="120" />
</p>

<h1 align="center">Spam Truyen Doc Viet</h1>
<p align="center"><strong>AI Story Audio Pipeline Studio</strong></p>

<p align="center">
  <img src="https://img.shields.io/badge/FastAPI-0.115+-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/UI-HTML%2FCSS%2FJS-0f172a?style=for-the-badge&logo=javascript&logoColor=f7df1e" alt="UI" />
  <img src="https://img.shields.io/badge/Stage-Convert%20%2B%20Audio-1d4ed8?style=for-the-badge" alt="Stage" />
  <img src="https://img.shields.io/badge/Runtime-Tested-16a34a?style=for-the-badge" alt="Runtime Tested" />
</p>

<p align="center">
  <a href="#quick-start">Quick Start</a> •
  <a href="#experience">Experience</a> •
  <a href="#output-journey">Output Journey</a> •
  <a href="#api-surface">API Surface</a> •
  <a href="#roadmap">Roadmap</a> •
  <a href="#documentation">Docs</a>
</p>

---


## Experience

<p align="center">
  <img src="https://raw.githubusercontent.com/ambrouse/img/main/icon2.svg" alt="Studio Preview" width="420" />
</p>

<table>
<tr>
<td width="50%" valign="top">

### What You Feel
- One-click pipeline execution.
- One convert button moves chapters all the way into TTS-ready TXT.
- Full-screen loadscene on app open.
- Full-screen running overlay during generation.
- Real-time progress for both Convert and TTS pipelines (stage, chapter/file count, percent from backend jobs).
- Project Center for status, rename, notes, delete, and active project selection.
- Download-ready outputs from the same control page.

</td>
<td width="50%" valign="top">

### What You Control
- Voice profile selection by folder name.
- Story URL collection, Gemini rewrite, text cleanup, chunking, and TTS TXT export.
- Shared project metadata in `project_registry/projects.json`.
- Clear all TXT input files.
- Clear auto output WAV files + manifest.
- Clear source-level audio/video artifacts.

</td>
</tr>
</table>

## Quick Start

### One command
```bash
bash setup.sh
```

`setup.sh` will create local virtual environments, install web/TTS dependencies,
install Playwright Chromium for browser automation, ensure `9router` is running,
open Chrome debug port `9222` with GPT + `https://apptruyenchu.pro`, prewarm the
TTS model, then start the web app.

### First-run requirements
- Windows: Python 3.12 is required for the prebuilt TTS wheels.
- Node.js/npm is required so setup can install `9router` with `npm install -g 9router`
  when it is not already available.
- Internet access is required on the first run to download Python packages,
  Playwright Chromium, `9router`, and Hugging Face TTS/audio model assets.

### Open app
- Default: `http://localhost:8080`
- If occupied: auto fallback to available port and printed in terminal.

## Runtime Snapshot

### Verified in real runtime
- `GET /api/health` -> `{"ok": true}`
- `GET /api/pipeline/audio/voices` -> folder-based profile list
- `POST /api/pipeline/audio/run` -> pipeline success
- Download APIs return file attachments correctly

## Project Flow

```text
auto_convert_text                       -> auto_text_to_voice -> auto_generate_video
(collect/rewrite per chapter/clean/chunk)  (production stage)
```

## Project Center

```text
project_registry/projects.json
  <- auto_convert_text updates raw/rewrite/chunk/export status
  <- auto_text_to_voice updates voice/model/audio manifest status
```

The web UI now starts from a project management workspace:

- select the active project.
- select or create a convert session.
- rename, add notes, and delete project records/artifacts.
- run convert and voice generation against the active project.
- run video generation and merge against the active project/session.
- rerun or delete a single session without deleting the long-term project.
- inspect text, audio, and video assets from one workspace.

Session artifacts are isolated by run:

```text
projects_workspace/projects/<project_id>/sessions/session_ch0001_to_ch0010/
```

## Output Journey

```text
TXT Inputs (*.txt)
  -> Per-file TTS (*.wav)
  -> Combined Audio (combined.wav)
  -> Artifact Store (source_full/audio, source_full/video)
  -> Download Center / Download API
```

### Current folders
- Project workspace: `projects_workspace/projects/<project_id>/`
- Project chapter URL list: `projects_workspace/projects/<project_id>/chapter_urls/urls_latest.txt`
- Session raw text: `projects_workspace/projects/<project_id>/sessions/<session_id>/chapters_text/raw/*.txt`
- Session rewritten text: `projects_workspace/projects/<project_id>/sessions/<session_id>/chapters_text/rewritten/*.txt`
- Session audio-clean text: `projects_workspace/projects/<project_id>/sessions/<session_id>/chapters_text/audio_clean/*.txt`
- Session chunks: `projects_workspace/projects/<project_id>/sessions/<session_id>/chapters_text/chunks/*.txt`
- Session TTS inputs: `projects_workspace/projects/<project_id>/sessions/<session_id>/tts_inputs/*.txt`
- Session video root: `projects_workspace/projects/<project_id>/sessions/<session_id>/video/`
- Session video prompts: `projects_workspace/projects/<project_id>/sessions/<session_id>/video/prompts/*.prompt.txt`
- Session video images: `projects_workspace/projects/<project_id>/sessions/<session_id>/video/images/*.png`
- Session rendered video: `projects_workspace/projects/<project_id>/sessions/<session_id>/video/story_silent.mp4`
- Session final merged video: `projects_workspace/projects/<project_id>/sessions/<session_id>/video/final_story.mp4`
- Legacy manual TTS text: `auto_text_to_voice/text/*.txt`
- Shared project registry: `project_registry/projects.json`
- Voice profiles: `auto_text_to_voice/voice/<profile_name>/`
- Output wav: `auto_text_to_voice/output/*.wav`
- Combined audio: `source_full/audio/combined.wav`
- Manifest: `auto_text_to_voice/output/manifest.json`

## API Surface

### Pipeline
- `GET /api/health`
- `POST /api/convert/run-full`
- `POST /api/convert/collect`
- `GET /api/projects`
- `GET /api/projects/{project_id}`
- `PUT /api/projects/{project_id}`
- `POST /api/projects/{project_id}/delete`
- `POST /api/projects/{project_id}/sessions/{session_id}/delete`
- `GET /api/jobs/{job_id}`
- `GET /api/convert/projects`
- `GET /api/convert/projects/{project_id}`
- `POST /api/convert/projects/{project_id}/rewrite`
- `POST /api/convert/projects/{project_id}/audio-clean`
- `POST /api/convert/projects/{project_id}/chunk`
- `POST /api/convert/projects/{project_id}/export-tts-text`
- `POST /api/convert/gemini-browser/start`
- `GET /api/projects/{project_id}/chapter-urls`
- `POST /api/projects/chapter-urls/save`
- `POST /api/projects/chapter-urls/clear`
- `GET /api/pipeline/audio/voices`
- `POST /api/pipeline/audio/run`
  - accepts optional `project_id` and `session_id`
- `POST /api/pipeline/video/prewarm`
- `POST /api/pipeline/video/analyze`
- `POST /api/pipeline/video/prompts`
- `POST /api/pipeline/video/images`
- `POST /api/pipeline/video/render`
- `POST /api/pipeline/video/merge`
- `POST /api/pipeline/video/run`

### File Operations
- `POST /api/files/clear/text`
- `POST /api/files/clear/auto-output-audio`
- `POST /api/files/clear/source-media`

### Download
- `GET /api/files/source-media`
- `GET /api/files/download/audio?filename=...`
- `GET /api/files/download/video?filename=...&project_id=...&session_id=...`

## Roadmap

### Phase 1 (Done)
- Audio pipeline control panel
- Voice profile scanning
- Merge output + manifest
- Clear operations + download center

### Phase 2 (Done)
- Unified collect -> Gemini rewrite -> clean -> chunk -> TTS TXT export

### Phase 2.1 (Planned)
- Job history + timeline UI
- Retry/cancel controls for long-running tasks

### Phase 2.2 (Done)
- Shared project registry
- Project Center UI
- TTS run metadata linked to active project
- Real Gemini web smoke test through Chrome remote debugging
- Per-session convert artifacts
- Real backend progress API for the run overlay

### Phase 3 (In Progress)
- Added in-project `Video` page with prompt/image/render/merge controls.
- Added session-first video pipeline under `auto_generate_video`.
- Added session-scoped video outputs and download routing.
- Image generation pipeline uses GPT web/image flow; local model setup is only required for audio/TTS.

## Documentation

- `docs/plan_audio_pipeline.md`
- `docs/architecture_audio_pipeline.md`
- `docs/plan_auto_convert_text_pipeline.md`
- `docs/architecture_auto_convert_text.md`
- `docs/test_report_auto_convert_text.md`
- `docs/test_report_audio_pipeline.md`
- `docs/audio_pipeline_web.md`
- `docs/project_management_ui.md`
- `docs/chapter_url_list_flow.md`
- `docs/logs.md`

## Design Assets

- Visual source (project rule): `https://github.com/ambrouse/img`

## Version

- `v0.1.0-audio-pipeline`
- Updated: `2026-05-01`

## License

Proprietary (Internal Use)
