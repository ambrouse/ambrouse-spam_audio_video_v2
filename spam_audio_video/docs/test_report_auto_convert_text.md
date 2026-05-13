# Runtime Test Report: Auto Convert Text

Date: 2026-04-29

## Test Matrix

1. Syntax validation
- Command:
  - `python -m py_compile auto_convert_text/models/dto.py auto_convert_text/adapters/base.py auto_convert_text/adapters/generic.py auto_convert_text/adapters/metruyenchu_com_vn.py auto_convert_text/adapters/metruyenchu_org.py auto_convert_text/adapters/metruyenchu_co.py auto_convert_text/adapters/truyenchucv_org.py auto_convert_text/storage/project_store.py auto_convert_text/pipeline/collector.py auto_convert_text/cli/run_convert.py source_full/backend/convert_service.py source_full/backend/server.py source_full/backend/pipeline_service.py auto_text_to_voice/vieneu_worker.py auto_text_to_voice/run_vieneu_batch_clone.py`
- Result: PASS

2. Collector runtime with local story server
- Flow:
  - Start temporary HTTP chapter pages.
  - Generate chapter URLs from an explicit increment segment such as `chuong-7`.
  - Generate chapter URLs from `/chuong-1.html`.
  - Generate chapter URLs from `/chuong-{chapter}.html`.
  - Save raw files under `auto_convert_text/data/projects/local-test-story/chapters_text/raw/`.
  - Write `chapters_manifest.json`.
- Result: PASS
- Assertions:
  - explicit increment segment mode success = 2
  - last-number URL mode success = 2
  - marker URL mode success = 2
  - failed = 0
  - manifest exists
  - every success chapter has non-empty `.txt`

3. FastAPI convert endpoint runtime
- Flow:
  - Start temporary HTTP story page.
  - `POST /api/convert/collect`
  - `GET /api/convert/projects/api-local-test`
- Result: PASS
- Assertions:
  - HTTP 200
  - `success_count = 1`
  - manifest summary success = 1

4. TTS frontend/backend default validation
- Result: PASS
- Assertions:
  - frontend displays `temperature: 0.80, top_k: 80, max_chars: 420, ref_clean: false`
  - removed frontend checkbox for cleaning reference audio
  - backend sends `preprocess_reference=false`

5. Frontend smoke test
- URL: `http://localhost:8081/`
- Result: PASS
- Assertions:
  - `GET /api/health` returns `{"ok": true}`
  - HTML contains Auto Convert Text panel
  - HTML contains TTS defaults from the requested image

6. Rewrite/Clean/Chunk/Export core runtime
- Flow:
  - Create temporary convert project with 2 raw chapter files.
  - Run `GeminiRewriter` with `FakeGeminiAdapter`.
  - Run `AudioCleaner`.
  - Run `Chunker`.
  - Run `TtsExporter` with `clear_old=True`.
  - Restore existing `auto_text_to_voice/text/*.txt` after test.
- Result: PASS
- Assertions:
  - rewrite success = 2
  - audio clean success = 2
  - chunks generated = 3
  - exported text files = 3
  - exported file content matches chunk source

7. Rewrite/Clean/Chunk/Export API runtime
- Flow:
  - Create temporary convert project with 1 raw chapter file.
  - `POST /api/convert/projects/{id}/rewrite`
  - `POST /api/convert/projects/{id}/audio-clean`
  - `POST /api/convert/projects/{id}/chunk`
  - `POST /api/convert/projects/{id}/export-tts-text`
- Result: PASS
- Assertions:
  - rewrite success = 1
  - audio clean success = 1
  - chunks generated >= 1
  - exported count equals chunk count

8. Frontend unified convert controls smoke test
- URL: `http://localhost:8081/`
- Result: PASS
- Assertions:
  - HTML contains `Run Convert To TTS TXT`
  - HTML contains `rewriteProviderSelect`
  - HTML does not expose old separate `Run Gemini Rewrite` / `Export To TTS Text` stage buttons

9. Endpoint rewrite control smoke test
- URL: `http://localhost:8081/`
- Result: PASS
- Assertions:
  - backend compile includes `/api/convert/gemini-browser/start`
  - full convert/rewrite flow runs via OpenAI-compatible endpoint mode (`provider=openai_compat`)
- Note:
  - Browser-launch tooling is legacy-only; production rewrite path is URL-only.

10. Unified full convert pipeline runtime
- Flow:
  - Start temporary HTTP chapter pages.
  - Run `ConvertPipelineService.run_full_to_tts_text`.
  - Generate chapter URLs from `chapter_token`.
  - Send each chapter once through `FakeGeminiAdapter`.
  - Clean text, split chunks, export into `auto_text_to_voice/text/`.
  - Restore existing `auto_text_to_voice/text/*.txt` after test.
- Result: PASS
- Assertions:
  - rewritten chapters = 2
  - exported text files >= 1
  - backend clamped tiny `max_chars` request to 300
  - largest exported file = 274 chars

11. Chunk hard-cap validation
- Flow:
  - Call `split_text_into_chunks` with small limits.
  - Validate every returned chunk length.
- Result: PASS
- Assertions:
  - max chunk length = 119 when `max_chars=180`
  - no chunk exceeded the configured hard cap

12. Unified frontend/backend HTTP smoke test
- URL: `http://127.0.0.1:8081/`
- Flow:
  - Fetch frontend HTML.
  - Assert Convert page exposes `Run Convert To TTS TXT`.
  - Assert TTS page exposes `Run Audio Pipeline`.
  - Assert old Convert auxiliary buttons `Refresh Projects` and `Load Manifest` are not exposed.
  - Assert old TTS clear buttons are not exposed on TTS Studio.
  - POST `/api/convert/run-full` with 2 local chapters and fake Gemini.
- Result: PASS
- Assertions:
  - rewritten chapters = 2
  - exported text files = 1
  - largest exported file = 260 chars

## Gemini Web Session Status

- Fake adapter runtime is fully tested and passing.
- Real Gemini web automation was smoke-tested through Chrome remote debugging on port `9222`.
- The adapter now filters visible Gemini editors, avoids hidden `ql-clipboard` nodes, and extracts only the latest answer after the matching prompt.
- Real Gemini full convert smoke with one local chapter passed:
  - collect success = 1
  - rewrite success = 1
  - exported TTS text files = 1
  - `auto_text_to_voice/text` was backed up and restored during the test.
- Real Gemini session full convert smoke passed after session refactor:
  - session id = `session_ch0001_to_ch0001`
  - rewrite success = 1
  - exported TTS text files = 1

## Project Manager Runtime

- Shared registry path: `project_registry/projects.json`
- Fake full pipeline + shared project CRUD + frontend smoke: PASS.
- Workspace root `projects_workspace/projects/<project_id>/sessions/<session_id>/`: PASS.
- Session text API rooted to active project/session: PASS.
- Per-convert session artifact layout: PASS.
- Session range metadata (`chapter_start`, `chapter_end`): PASS.
- Session delete removes corresponding convert artifacts and exported session TTS text files: PASS.
- Backend progress API with real stage/file units: PASS.
- Live frontend sessions/progress smoke: PASS.
- `GET /api/projects`: PASS.
- `PUT /api/projects/{project_id}`: PASS.
- `POST /api/projects/{project_id}/delete`: PASS.
- `POST /api/projects/{project_id}/sessions/{session_id}/delete`: PASS.
- `GET /api/jobs/{job_id}`: PASS.
- Frontend contains Project Center, Convert, Voice, and Assets pages: PASS.

## Conclusion

Current milestone passes 100% for local deterministic runtime:

```text
URL -> chapter files -> manifest -> fake Gemini rewrite per chapter -> audio clean -> chunk -> export TTS text -> frontend/backend API integration
```

Real Gemini smoke now also passes when Chrome remote debugging is available and the Gemini profile is logged in.
