#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

MODE="${1:-web}" # web | stream | example
IS_WSL="0"
if grep -qi microsoft /proc/version 2>/dev/null; then
  IS_WSL="1"
fi
VENV_DIR=".venv"
export GRADIO_SERVER_PORT="${GRADIO_SERVER_PORT:-7861}"

echo "[VieNeu-TTS] Project root: $ROOT_DIR"
echo "[VieNeu-TTS] Mode: $MODE"
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

if command -v uv >/dev/null 2>&1; then
  echo "[1/3] Sync dependencies with uv..."
  uv sync

  echo "[2/3] Run project..."
  case "$MODE" in
    web)
      uv run vieneu-web
      ;;
    stream)
      uv run vieneu-stream
      ;;
    example)
      uv run python examples/main.py
      ;;
    *)
      echo "Mode khong hop le: $MODE"
      echo "Dung: ./run_project.sh [web|stream|example]"
      exit 1
      ;;
  esac
else
  echo "[1/3] Khong tim thay uv, fallback sang venv + pip..."
  # Prefer Windows launcher when running in Git Bash/WSL to avoid Linux python3-venv issues.
  if command -v py.exe >/dev/null 2>&1 && py.exe -3 --version >/dev/null 2>&1; then
    PYTHON_CMD=("py.exe" "-3")
  elif command -v py >/dev/null 2>&1 && py -3 --version >/dev/null 2>&1; then
    PYTHON_CMD=("py" "-3")
  elif command -v py >/dev/null 2>&1 && py --version >/dev/null 2>&1; then
    PYTHON_CMD=("py")
  elif command -v python3 >/dev/null 2>&1 && python3 --version >/dev/null 2>&1; then
    PYTHON_CMD=("python3")
  elif command -v python >/dev/null 2>&1 && python --version >/dev/null 2>&1; then
    PYTHON_CMD=("python")
  else
    echo "Khong tim thay Python launcher hoat dong (py/python3/python)."
    echo "Goi y: cai Python tu python.org va tick 'Add python.exe to PATH'."
    exit 1
  fi

  if [ "$IS_WSL" = "1" ] && [[ "${PYTHON_CMD[0]}" == "py.exe" ]]; then
    VENV_DIR=".venv-win"
  fi

  if [ ! -d "$VENV_DIR" ] || { [ ! -f "$VENV_DIR/Scripts/python.exe" ] && [ ! -f "$VENV_DIR/bin/python" ]; }; then
    rm -rf "$VENV_DIR"
    if [ "$IS_WSL" = "1" ] && [[ "${PYTHON_CMD[0]}" == "py.exe" ]]; then
      WIN_ROOT="$(wslpath -w "$ROOT_DIR")"
      "${PYTHON_CMD[@]}" -m venv "${WIN_ROOT}\\${VENV_DIR}"
    else
      "${PYTHON_CMD[@]}" -m venv "$VENV_DIR"
    fi
  fi

  if [ -f "$VENV_DIR/Scripts/python.exe" ]; then
    VENV_PY="$VENV_DIR/Scripts/python.exe"
  elif [ -f "$VENV_DIR/bin/python" ]; then
    VENV_PY="$VENV_DIR/bin/python"
  else
    echo "Khong tim thay python trong $VENV_DIR."
    exit 1
  fi

  echo "[2/3] Install dependencies with pip..."
  if ! "$VENV_PY" -m pip --version >/dev/null 2>&1; then
    echo "pip chua san sang trong $VENV_DIR, tao lai venv..."
    rm -rf "$VENV_DIR"
    if [ "$IS_WSL" = "1" ] && [[ "${PYTHON_CMD[0]}" == "py.exe" ]]; then
      WIN_ROOT="$(wslpath -w "$ROOT_DIR")"
      "${PYTHON_CMD[@]}" -m venv "${WIN_ROOT}\\${VENV_DIR}"
    else
      "${PYTHON_CMD[@]}" -m venv "$VENV_DIR"
    fi
    if [ -f "$VENV_DIR/Scripts/python.exe" ]; then
      VENV_PY="$VENV_DIR/Scripts/python.exe"
    else
      VENV_PY="$VENV_DIR/bin/python"
    fi
  fi

  "$VENV_PY" -m pip install -U pip setuptools wheel
  # Prefer prebuilt llama-cpp wheel on Windows to avoid local C/C++ build toolchain issues.
  if [[ "$VENV_PY" == *"Scripts/python.exe" ]]; then
    "$VENV_PY" -m pip install \
      "https://github.com/pnnbao97/VieNeu-TTS/releases/download/wheels-v0.3.16/llama_cpp_python-0.3.16-cp312-cp312-win_amd64.whl"
  fi
  "$VENV_PY" -m pip install -e .
  "$VENV_PY" -m pip install "gradio>=5.49.1,<6"

  echo "[3/3] Run project..."
  case "$MODE" in
    web)
      "$VENV_PY" -m apps.gradio_main
      ;;
    stream)
      "$VENV_PY" -m apps.web_stream
      ;;
    example)
      "$VENV_PY" examples/main.py
      ;;
    *)
      echo "Mode khong hop le: $MODE"
      echo "Dung: ./run_project.sh [web|stream|example]"
      exit 1
      ;;
  esac
fi
