# Project Docs Index (Compact)

## Core
- `README.md`: high-level product story, quick start, runtime snapshot.
- `agens/flow_code_skill.md`: engineering rules and delivery flow.

## Architecture
- `docs/architecture_audio_pipeline.md`: TTS/audio service architecture.
- `docs/architecture_auto_convert_text.md`: chapter collect/convert architecture.
- `docs/architecture_rewrite_chunk_tts_export.md`: rewrite-clean-chunk-export flow.

## Plans
- `docs/plan_product_web_refactor_localfile.md`: master product refactor plan (active).
- `docs/plan_audio_pipeline.md`: legacy audio phase plan.
- `docs/plan_auto_convert_text_pipeline.md`: legacy convert plan.
- `docs/plan_breath_chunk_antileak.md`: quality optimization plan.

## Runtime / Ops
- `docs/gpu_runtime_2026-05-14.md`: current GPU-only audio/video runtime contract and clone defaults.
- `../docs/portable_windows_release.md`: Windows portable app build/release contract.
- `../docs/release_notes_v0.1.6.md`: clean production story timeline and long-run stability release notes.
- `../docs/native_full_timeline_2026-05-17.md`: current production Rust/D3D11/NVENC full-timeline video path and 3-minute validation.
- `docs/test_report_audio_pipeline.md`: runtime validations for audio stage.
- `docs/test_report_auto_convert_text.md`: runtime validations for convert stage.
- `docs/test_report_video_pipeline.md`: runtime validations for video stage.
- `docs/logs.md`: compact changelog.

## UI and Flow
- `docs/project_management_ui.md`: project/session UI contract.
- `docs/chapter_url_list_flow.md`: chapter URL lifecycle.
- `docs/audio_pipeline_web.md`: web controller operation notes.

## Active Direction (Current)
1. Project-first UX + session-first operations.
2. Full run-all orchestration with safe stop.
3. GPU-only production runtime for TTS/video: fail fast when CUDA/NVENC path is not ready.
4. Browser bridge owns port opening; GPT/video config only references bridge ports.
5. Logs governance and knowledge hub.
