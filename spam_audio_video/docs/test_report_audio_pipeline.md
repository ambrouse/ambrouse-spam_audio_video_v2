# Runtime Test Report

Date: 2026-04-28

## Test matrix
1. Compile check
- Command: `python -m compileall auto_text_to_voice/run_vieneu_batch_clone.py source_full/backend/server.py source_full/backend/pipeline_service.py`
- Result: PASS

2. Direct pipeline runtime test
- Command:
  - `python auto_text_to_voice/run_vieneu_batch_clone.py --project-root auto_text_to_voice/VieNeu-TTS --voice-dir auto_text_to_voice/voice --text-dir auto_text_to_voice/text --output-dir auto_text_to_voice/output --combined-output source_full/audio/combined.wav --manifest-path auto_text_to_voice/output/manifest.json`
- Result: PASS
- Assertions:
  - Per-text wav output generated.
  - Merged file generated at `source_full/audio/combined.wav`.
  - Manifest generated at `auto_text_to_voice/output/manifest.json`.

3. API runtime test
- Command:
  - `python -c "from fastapi.testclient import TestClient; import sys; sys.path.insert(0, 'source_full/backend'); import server; c=TestClient(server.app); print(c.get('/api/health').json()); print(c.post('/api/pipeline/audio/run').status_code)"`
- Result: PASS
- Assertions:
  - `GET /api/health` returns `{"ok": true}`.
  - `POST /api/pipeline/audio/run` returns HTTP 200 and success response.

## Conclusion
All current-scope tests passed with real runtime execution.

---

Date: 2026-04-29

## Extended runtime matrix (rule-based re-test)
1. Syntax validation
- Command: `python -m py_compile auto_text_to_voice/run_vieneu_batch_clone.py auto_text_to_voice/audio_postprocess.py source_full/backend/server.py source_full/backend/pipeline_service.py source_full/run_web.py`
- Result: PASS

2. Runtime environment check (pipeline venv)
- Command: Python probe in `auto_text_to_voice/VieNeu-TTS/.venv-win`
- Result:
  - `torch_version=2.11.0+cpu`
  - `cuda_available=False`
- Verdict: PASS for environment detection, GPU unavailable on current runtime.

3. End-to-end pipeline test: profile `thien-vuong`
- Command: batch clone with `--device auto --postprocess --preprocess-reference`
- Result: PASS
- Assertions:
  - `manifest.voice_profile=thien-vuong`
  - `manifest.mode=turbo`
  - `manifest.device=cpu`
  - outputs: `text1.wav`, `text2.wav`, `combined.wav` generated
  - sample rate outputs: `24000 Hz`

4. End-to-end pipeline test: profile `phe_phim`
- Command: batch clone with `--device auto --postprocess --preprocess-reference`
- Result: PASS
- Assertions:
  - `manifest.voice_profile=phe_phim`
  - `manifest.mode=turbo`
  - `manifest.device=cpu`
  - outputs: `text1.wav`, `text2.wav`, `combined.wav` generated
  - sample rate outputs: `24000 Hz`

## Pass criteria status
- Compile/syntax: PASS
- Runtime execution: PASS
- Output artifacts: PASS
- Manifest integrity: PASS
- GPU execution: NOT PASS (blocked by runtime environment: CUDA not available in current venv)

---

Date: 2026-04-30

## VoxCPM migration runtime matrix
1. Worker model catalog check
- Command: Python probe via `AudioPipelineService.list_models()`
- Result: PASS
- Assertion:
  - only one model returned: `voxcpm_vn`
  - selected model is `voxcpm_vn`

2. Initial compatibility failure discovery
- Command: runtime `set_model('voxcpm_vn')` against old VieNeu-based load path
- Result: FAIL (expected during migration)
- Error:
  - `Unrecognized model in JayLL13/VoxCPM-1.5-VN. Should have a model_type key in config.json.`
- Action:
  - replaced VieNeu loading path with native `voxcpm` runtime.

3. Native VoxCPM runtime test (direct)
- Command: `.venv-win` Python script with `VoxCPM.from_pretrained('JayLL13/VoxCPM-1.5-VN')` + `generate(...)`
- First result: FAIL
- Error:
  - `Could not load libtorchcodec` (Windows torchcodec/ffmpeg dependency path)
- Fix:
  - patched worker `torchaudio.load` to stable `soundfile` loader.
- Re-test result: PASS
- Assertion:
  - generated waveform shape returned (float32, non-empty).

4. Worker synth command test (real worker IPC)
- Command: `AudioPipelineService._send_worker({"cmd":"synth", ... "model_key":"voxcpm_vn"})` with one txt input
- Result: PASS
- Assertions:
  - reply `ok=True`
  - `manifest.mode=voxcpm`
  - `manifest.model_key=voxcpm_vn`
  - one wav file generated
  - merged output generated

5. Backend integration run test
- Command: `AudioPipelineService.run(project_id='voxcpm-integration-test', session_id='session_ch0001_to_ch0001', model_key='voxcpm_vn')`
- Result: PASS
- Assertions:
  - `success=True`
  - `projects_workspace/.../audio/manifest.json` exists
  - `projects_workspace/.../audio/combined.wav` exists

## Conclusion
VoxCPM single-model pipeline is now runtime-stable on this machine with native `voxcpm` engine and worker-level audio loader patch.

---

Date: 2026-05-01

## TTS parallel IO smoke test
1. Syntax validation
- Command: `python -m compileall source_full/backend/server.py source_full/backend/pipeline_service.py auto_text_to_voice/vieneu_worker.py`
- Result: PASS

2. Runtime worker smoke (2 files, io_workers=2)
- Command: Python probe through `AudioPipelineService._send_worker({... "cmd":"synth", "io_workers":2 ...})` with temporary text/output dirs.
- Result: PASS
- Assertions:
  - reply `ok=True`
  - `manifest.outputs` count = `2`
  - `manifest.io_workers` = `2`
  - merged output created successfully
