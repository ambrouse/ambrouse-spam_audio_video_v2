#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

if [[ -f "VieNeu-TTS/.venv-win/Scripts/python.exe" ]]; then
  PY="VieNeu-TTS/.venv-win/Scripts/python.exe"
elif [[ -f "VieNeu-TTS/.venv/Scripts/python.exe" ]]; then
  PY="VieNeu-TTS/.venv/Scripts/python.exe"
elif command -v py.exe >/dev/null 2>&1; then
  PY="py.exe -3"
elif command -v python3 >/dev/null 2>&1; then
  PY="python3"
else
  PY="python"
fi

echo "Using Python: $PY"
echo "[1/3] Start project backend via VieNeu-TTS/run_project.sh ..."

BACKEND_LOG="VieNeu-TTS/.batch_backend.log"
mkdir -p "VieNeu-TTS"

# Run backend in background
bash "VieNeu-TTS/run_project.sh" web > "$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!

cleanup() {
  if kill -0 "$BACKEND_PID" >/dev/null 2>&1; then
    kill "$BACKEND_PID" >/dev/null 2>&1 || true
    sleep 1
    kill -9 "$BACKEND_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

echo "Backend PID: $BACKEND_PID"
echo "[2/3] Wait backend ready on localhost (7860-7879) ..."
sleep 8
# In mixed WSL/Windows setups, localhost health-check can fail even when backend is running.
# So we only do best-effort check and continue.
READY=0
for p in $(seq 7860 7879); do
  if curl -fsS "http://127.0.0.1:${p}/" >/dev/null 2>&1; then
    echo "Backend ready at http://127.0.0.1:${p}"
    READY=1
    break
  fi
done
if [[ "$READY" -ne 1 ]]; then
  echo "Backend warm-up done (skip strict HTTP check in this shell environment)."
fi

echo "[3/3] Run batch clone ..."
if [[ "$PY" == *" "* ]]; then
  # Handle "py.exe -3"
  eval "$PY run_vieneu_batch_clone.py --project-root VieNeu-TTS --voice-dir voice --text-dir text --output-dir output"
else
  "$PY" run_vieneu_batch_clone.py --project-root VieNeu-TTS --voice-dir voice --text-dir text --output-dir output
fi

echo "Done. Output files are in ./output"
