# Real Runtime Checklist (Endpoint Parallel)

Date: 2026-05-01

## Preconditions
1. Start web app:
- `bash setup.sh`

2. Ensure OpenAI-compatible router endpoint is running:
- `http://localhost:20128/v1`

3. In frontend Convert page:
- Set `LLM endpoint` to `http://localhost:20128/v1`.
- Set `LLM model` to your router-supported model (default: `gemini/gemini-3-flash-preview`).
- Set `Rewrite workers` to desired parallel level.

4. Manual action required by you:
- Verify router logs show incoming requests before running long jobs.
- Keep endpoint healthy during the run.

## Real test cases

### TC1: Parallel rewrite real
- Select active project/session with raw chapters ready.
- Click `Rewrite only` (provider `openai_compat` + parallel settings).
- Expected:
  - rewrite_manifest shows success count > 0,
  - throughput faster than single-worker run.

### TC2: Safe stop
- While rewrite is running, click `Stop`.
- Expected:
  - no new chapter scheduling after stop signal,
  - job status becomes `stopped`.

### TC3: Emergency stop
- Re-run rewrite, then click `Emergency Stop`.
- Expected:
  - stop status transitions to `force_stopped`.

### TC4: Resume checkpoint
- Click `Run All Resume`.
- Expected:
  - only pending/unprocessed files are rewritten,
  - pipeline continues clean -> tts_inputs -> tts.

### TC5: Log governance
- Open Knowledge page.
- Run `Query Logs` and `Apply Retention`.
- Expected:
  - logs query returns rows,
  - retention trims old/excess log files.

## Evidence to capture
- Router request log sample.
- rewrite_manifest summary before/after stop/resume.
- job stop-status payload.
- final TTS manifest and combined audio timestamp.
