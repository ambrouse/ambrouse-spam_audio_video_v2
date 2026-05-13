# Development Plan

## Phase 1 - Analyze rules and current repo
- Goal: compare implementation against `agens/flow_code_skill.md`.
- Pass criteria:
  - Rule gaps are identified.
  - Existing audio pipeline flow is mapped end-to-end.

## Phase 2 - Refactor code for pipeline quality
- Goal: keep existing behavior and improve production structure for current scope.
- Tasks:
  - Keep batch txt -> wav conversion.
  - Keep merged output into `source_full/audio/combined.wav`.
  - Add backend request guard to avoid duplicate concurrent runs.
  - Improve frontend UX with load bar + motion.
- Pass criteria:
  - API endpoint still triggers complete pipeline.
  - Output/manifest paths are stable and deterministic.

## Phase 3 - Runtime test and fix
- Goal: verify real runtime behavior (not only syntax checks).
- Tasks:
  - Run pipeline script with actual text + voice sample.
  - Run API health and API run tests.
  - Ensure merged audio exists after run.
- Pass criteria:
  - All runtime checks pass 100%.

## Phase 4 - Documentation and operation
- Goal: make project reproducible for new machine setup.
- Tasks:
  - Add `.gitignore`.
  - Add `setup.sh` one-command bootstrap/run script.
  - Update README with badges, architecture, run guide, and roadmap.
  - Add logs/test reports in docs.
- Pass criteria:
  - New contributor can follow docs and run project from scratch.
