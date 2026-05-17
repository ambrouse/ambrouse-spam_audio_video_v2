# Change Log (Compact)

## 2026-05-14
- GPT image generation now submits scene prompts as a bridge batch, allowing the bridge scheduler to keep ready ports busy and cooldown limited ports.
- Video prompt generation now uses parallel bridge requests through the same port scheduler.
- Video render defaults to `VIDEO_RENDER_WORKERS=6`, and the UI exposes `Render workers`.
- GPU runtime hardened for production: audio defaults to CUDA and fails fast when the TTS venv has CPU-only PyTorch.
- Video encoder selection is GPU-only; `auto` verifies hardware H.264 encoders and CPU `libx264` is blocked.
- GPU Setting UI now shows a short runtime conclusion instead of raw JSON.
- GPT/video config no longer opens ports; bridge port opening stays in the Bridge tab.
- Added `.env.example` with GPU-safe defaults and wired `.env` loading for setup/web runtime.
- Text cleanup/chunk/export now preserve only `.` and `,`; other punctuation is deleted instead of replaced.

## 2026-05-17
- Video main path moved from segmented clip render/combine to a Rust/D3D11/NVENC full-timeline renderer for 16:9 60fps h264_nvenc outputs.
- FFmpeg remains in the main path only for MP4 remux/final audio mux; the image motion, overlay, visualizer, and timeline transitions are shader-native.
- 3-minute 4K60 with-audio validation completed in `94.291s` total video stage, with `87.908s` in story timeline render and about `421 MB` renderer peak working set.
- Fast HD profile added: web/backend defaults now target `1080p60`, story renderer throughput maps to NVENC `p1`, bitrate scales per resolution, and a 3-minute 1080p60 with-audio validation completed in `23.305s` total video stage.
- Native visual polish changed audio bars to circular two-side dot clusters and changed dust/spark overlays to vertical-only soft circular particles; 3-minute 1080p60 validation completed in `22.701s`.
- Audio aggressive profile added: VoxCPM now uses inference-mode/TF32 runtime hints, defaults to `6` inference steps with `retry_badcase_max_times=1`, and streams final WAV merge to keep RAM stable on long runs. Full current-session audio improved from `1114.424s` to `1102.582s`; speed gain is small because model inference dominates.
- Video cleanup completed: the main `render_video()` path now only uses the production Rust/D3D11/NVENC full-timeline renderer, old segmented clip/FFmpeg combine fallback code was removed, and a fresh 3-minute 1080p60 with-audio validation completed in `22.623s`.
- Long-run stability guard added: CI now checks audio merge stays streaming, old segmented video tokens stay out of runtime source, and Windows builds/tests the Rust story renderer.

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
- Phase 15: session artifact contract originally exposed legacy silent/final filenames; current production releases use `story_render*.mp4` and `story_render*_with_audio.mp4`.
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
