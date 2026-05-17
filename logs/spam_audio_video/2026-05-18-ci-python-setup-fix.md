# 2026-05-18 CI Python Setup Fix

## Scope

- Fixed the failing GitHub Actions `CI / python-and-setup` job on the
  `v0.1.6` production story pipeline commit.

## Root Cause

- The job ran unit tests in a clean Ubuntu Python environment.
- `test_video_render_planning.py` imports `auto_generate_video.pipeline`.
- That module imports `auto_convert_text.pipeline.browser_bridge_client`, which
  imports `httpx`.
- Local validation passed because `httpx` was already installed locally, but CI
  did not install any unit-test dependencies before `python -m unittest`.

## Fix

- Added a lightweight CI step before unittest:
  `python -m pip install httpx`.
- Kept this narrow instead of installing the full app runtime because the CI
  test only needs the bridge client import dependency.

## Validation

- To be verified by the next `main` push GitHub Actions run.
