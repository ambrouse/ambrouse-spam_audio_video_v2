# Change Log (Compact)

## 2026-05-01
- Phase 1: safe stop/emergency stop, run-all, logs + knowledge APIs, frontend controls.
- Phase 2: parallel rewrite config, chrome pool open/close, frontend pool controls.
- Phase 3: pool status + login-ready, persisted pool state, parallel rewrite runtime validation.
- Phase 4: resume checkpoint mode, stop-aware rewrite scheduler, run-all resume API + frontend action.
- Phase 5: logs retention API + frontend retention action; real runtime checklist.
- Phase 6: stop controls added directly to load overlay; prompt-echo sanitization hardened.
- Phase 7: knowledge APIs completed (`reindex`, `file-meta get/patch`) with catalog merge.
- Phase 8: implemented project-first workspace open flow with aggregate preload API (`/api/workspace/projects/{project_id}/open`) and frontend project-context gate integration.
- Phase 9: added chapter manager API set (list/add/patch/delete with URL normalize+dedupe) and prompt-default CRUD (`/api/prompt-default`).
- Phase 10: added per-file session-stage CRUD APIs (`PATCH/DELETE /api/projects/{project_id}/sessions/{session_id}/file`) and wired Session Explorer UI for load/new/save/delete.
- Phase 11: hardened project-first gate in frontend (changing project now requires explicit reopen) and added `apply_chapter_window` flag for collect/run-all to avoid unintended auto-trim of full crawled chapter URL lists.

## 2026-05-03
- Phase 12: added session-first video pipeline core in `auto_generate_video` (analyze/prompt/image/render/merge/full-run).
- Phase 13: added backend `VideoPipelineService` and FastAPI endpoints `/api/pipeline/video/*` with job progress integration.
- Phase 14: added in-project frontend `Video` page with controls for timing, prompt provider, SD runtime config, render, and merge.
- Phase 15: session artifact contract updated so each session includes `video/` subtree and downloadable `story_silent.mp4` + `final_story.mp4` at session video root.
- Phase 16: runtime hardening added for missing `combined.wav` (duration/merge fallback from per-file wavs) and fake-mode placeholder image generation for smoke tests when SD runtime is not yet configured.
- Phase 17: video runtime fix pack for production use: placeholder images are now opt-in only (`VIDEO_ALLOW_PLACEHOLDER=1`), Gemini image-prompt sanitization improved (handles `Prompt:`/`Final prompt:` wrappers), render camera zoom motion slowed down 5x, and render stage now also exports an audio-attached video variant (`*_with_audio.mp4`).
- Phase 18: rewrite runtime now supports OpenAI-compatible endpoint mode (`provider=openai_compat`) with defaults `http://localhost:20128/v1` + `gemini/gemini-3-flash-preview`; backend/frontend defaults switched away from Chrome CDP for rewrite flow.
- Phase 19: removed `gemini_web` routing from video prompt generation; video prompt flow is now URL-only (`openai_compat`) and writes endpoint/model trace into `video/manifests/prompts_manifest.json` for future runtime audits.

## Reports
- `docs/test_report_product_refactor_phase1.md`
- `docs/test_report_product_refactor_phase2.md`
- `docs/test_report_product_refactor_phase3.md`
- `docs/test_report_product_refactor_phase4.md`
- `docs/test_report_product_refactor_phase5.md`
- `docs/test_report_product_refactor_phase6.md`
- `docs/test_report_product_refactor_phase7.md`
- `docs/real_runtime_checklist_gemini_parallel.md`
