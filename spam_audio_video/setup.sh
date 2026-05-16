#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
  set +a
fi

LOG_DIR="$ROOT_DIR/.logs"
mkdir -p "$LOG_DIR"
SETUP_LOG="$LOG_DIR/setup_$(date +%Y%m%d_%H%M%S).log"

STEP_INDEX=0
STEP_TOTAL=11
STEP_TASK_DONE=0
STEP_TASK_TOTAL=1
STEP_TITLE=""
STEP_BAR_OPEN=0

if [[ -t 1 ]]; then
  C_RESET=$'\033[0m'
  C_BOLD=$'\033[1m'
  C_DIM=$'\033[2m'
  C_CYAN=$'\033[36m'
  C_GREEN=$'\033[32m'
  C_RED=$'\033[31m'
  C_BLUE=$'\033[34m'
else
  C_RESET=""
  C_BOLD=""
  C_DIM=""
  C_CYAN=""
  C_GREEN=""
  C_RED=""
  C_BLUE=""
fi

usage() {
  cat <<'EOF'
Usage:
  bash setup.sh [options]

Options:
  --install-only                 Install/validate runtime without starting the web controller.
  --yes, -y                      Answer yes to setup prompts.
  --production-validate          Run real one-chunk VoxCPM production validation.
  --skip-production-validation   Skip production validation.
  --tts-device auto|cuda|cpu     Select TTS runtime target. Default: auto.
  --help, -h                     Show this help.

Environment:
  SETUP_INSTALL_ONLY=1
  SETUP_ASSUME_YES=1
  SETUP_PRODUCTION_VALIDATE=1
  SETUP_SKIP_PRODUCTION_VALIDATE=1
  SETUP_TTS_DEVICE=auto|cuda|cpu
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --install-only)
      export SETUP_INSTALL_ONLY=1
      ;;
    --yes|-y)
      export SETUP_ASSUME_YES=1
      ;;
    --production-validate)
      export SETUP_PRODUCTION_VALIDATE=1
      ;;
    --skip-production-validation)
      export SETUP_SKIP_PRODUCTION_VALIDATE=1
      ;;
    --tts-device)
      shift
      if [[ $# -eq 0 ]]; then
        echo "[ERROR] --tts-device requires auto, cuda, or cpu."
        exit 1
      fi
      export SETUP_TTS_DEVICE="$1"
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "[ERROR] Unknown option: $1"
      usage
      exit 1
      ;;
  esac
  shift
done

if [[ "${SETUP_INSTALL_ONLY:-0}" == "1" ]]; then
  STEP_TOTAL=9
fi

UTF8_OK=0
case "${LC_ALL:-${LC_CTYPE:-${LANG:-}}}" in
  *UTF-8*|*utf8*|*utf-8*) UTF8_OK=1 ;;
esac

icon() {
  case "$1" in
    ok) printf "[OK]" ;;
    run) printf "[..]" ;;
    fail) printf "[X]" ;;
    info) printf "[i]" ;;
    rocket) printf "[>]" ;;
    port) printf "[#]" ;;
    *) printf "[*]" ;;
  esac
}
pad_right() {
  local text="$1"
  local width="$2"
  printf "%-${width}s" "$text"
}

truncate_text() {
  local text="$1"
  local width="$2"
  local len=${#text}
  if (( len <= width )); then
    printf "%s" "$text"
    return
  fi
  if (( width <= 3 )); then
    printf "%s" "${text:0:width}"
    return
  fi
  printf "%s..." "${text:0:width-3}"
}

term_cols() {
  local cols=100
  if command -v tput >/dev/null 2>&1; then
    cols="$(tput cols 2>/dev/null || echo 100)"
  fi
  if [[ -z "$cols" || "$cols" -lt 72 ]]; then
    cols=72
  fi
  if [[ "$cols" -gt 120 ]]; then
    cols=120
  fi
  echo "$cols"
}

progress_bar() {
  local done="$1"
  local total="$2"
  local pct width fill empty
  pct=$(( done * 100 / total ))
  width=28
  fill=$(( pct * width / 100 ))
  empty=$(( width - fill ))
  local left right
  left="$(printf '%*s' "$fill" '' | tr ' ' '#')"
  right="$(printf '%*s' "$empty" '' | tr ' ' '-')"
  printf "[%s%s]" "$left" "$right"
}

print_header() {
  local cols inner border title root_line log_line
  cols="$(term_cols)"
  inner=$(( cols - 4 ))
  border="$(printf '%*s' "$inner" '' | tr ' ' '=')"

  title="$(truncate_text "Audio Pipeline Setup" "$inner")"
  root_line="$(truncate_text "Root: $ROOT_DIR" "$inner")"
  log_line="$(truncate_text "Log : $SETUP_LOG" "$inner")"

  echo
  echo "   █████╗ ███╗   ███╗██████╗ ██████╗  ██████╗ ██╗   ██╗███████╗███████╗"
  echo "  ██╔══██╗████╗ ████║██╔══██╗██╔══██╗██╔═══██╗██║   ██║██╔════╝██╔════╝"
  echo "  ███████║██╔████╔██║██████╔╝██████╔╝██║   ██║██║   ██║███████╗█████╗  "
  echo "  ██╔══██║██║╚██╔╝██║██╔══██╗██╔══██╗██║   ██║██║   ██║╚════██║██╔══╝  "
  echo "  ██║  ██║██║ ╚═╝ ██║██████╔╝██║  ██║╚██████╔╝╚██████╔╝███████║███████╗"
  echo "  ╚═╝  ╚═╝╚═╝     ╚═╝╚═════╝ ╚═╝  ╚═╝ ╚═════╝  ╚═════╝ ╚══════╝╚══════╝"
  echo
  echo
  printf "+%s+\n" "$border"
  printf "| %s |\n" "$(pad_right "$title" "$inner")"
  printf "+%s+\n" "$border"
  printf "| %s |\n" "$(pad_right "$root_line" "$inner")"
  printf "| %s |\n" "$(pad_right "$log_line" "$inner")"
  printf "+%s+\n" "$border"
  echo
}

print_header_clean() {
  local cols inner border title root_line log_line
  cols="$(term_cols)"
  inner=$(( cols - 4 ))
  border="$(printf '%*s' "$inner" '' | tr ' ' '=')"

  title="$(truncate_text "Ambrouse Audio Pipeline Setup" "$inner")"
  root_line="$(truncate_text "Root: $ROOT_DIR" "$inner")"
  log_line="$(truncate_text "Log : $SETUP_LOG" "$inner")"

  echo
  printf "+%s+\n" "$border"
  printf "| %s |\n" "$(pad_right "$title" "$inner")"
  printf "+%s+\n" "$border"
  printf "| %s |\n" "$(pad_right "$root_line" "$inner")"
  printf "| %s |\n" "$(pad_right "$log_line" "$inner")"
  printf "+%s+\n" "$border"
  echo
}

render_step_bar() {
  local pct=$(( STEP_TASK_DONE * 100 / STEP_TASK_TOTAL ))
  printf "\r\033[2K%s[%3d%%]%s %s %s[%d/%d]%s %s" \
    "$C_CYAN" "$pct" "$C_RESET" "$(progress_bar "$STEP_TASK_DONE" "$STEP_TASK_TOTAL")" "$C_BOLD" "$STEP_INDEX" "$STEP_TOTAL" "$C_RESET" "$STEP_TITLE"
}

step() {
  local title="$1"
  local task_total="${2:-1}"
  if [[ "$STEP_BAR_OPEN" -eq 1 ]]; then
    printf "\n"
    STEP_BAR_OPEN=0
  fi
  STEP_INDEX=$((STEP_INDEX + 1))
  STEP_TITLE="$title"
  STEP_TASK_DONE=0
  STEP_TASK_TOTAL="$task_total"
  if (( STEP_TASK_TOTAL < 1 )); then
    STEP_TASK_TOTAL=1
  fi
  echo
  render_step_bar
  STEP_BAR_OPEN=1
}

step_tick() {
  if (( STEP_TASK_DONE < STEP_TASK_TOTAL )); then
    STEP_TASK_DONE=$((STEP_TASK_DONE + 1))
  fi
  render_step_bar
  if (( STEP_TASK_DONE >= STEP_TASK_TOTAL )); then
    printf "\n"
    STEP_BAR_OPEN=0
  fi
}

run_quiet() {
  local _msg="$1"
  shift
  "$@" >>"$SETUP_LOG" 2>&1
}

run_quiet_or_fail() {
  local msg="$1"
  shift
  if ! run_quiet "$msg" "$@"; then
    printf "\n%s %s%s failed.%s\n" "$(icon fail)" "$C_RED" "$msg" "$C_RESET"
    echo "Recent log lines:"
    tail -n 80 "$SETUP_LOG" || true
    exit 1
  fi
  step_tick
}

run_quiet_or_warn() {
  local msg="$1"
  shift
  if ! run_quiet "$msg" "$@"; then
    printf "\n%s %s%s skipped (non-fatal).%s\n" "$(icon info)" "$C_BLUE" "$msg" "$C_RESET"
    echo "Recent log lines:"
    tail -n 40 "$SETUP_LOG" || true
  fi
  step_tick
}

ask_yes_no() {
  local prompt="$1"
  local default="${2:-n}"
  local suffix="[y/N]"
  local answer
  if [[ "${default,,}" == "y" ]]; then
    suffix="[Y/n]"
  fi
  if [[ "${SETUP_ASSUME_YES:-0}" == "1" || "${CI:-0}" == "1" ]]; then
    echo "$prompt $suffix -> yes (SETUP_ASSUME_YES/CI)" >>"$SETUP_LOG"
    return 0
  fi
  while true; do
    printf "%s %s " "$prompt" "$suffix"
    if ! read -r answer; then
      answer="$default"
    fi
    answer="${answer:-$default}"
    case "${answer,,}" in
      y|yes) return 0 ;;
      n|no) return 1 ;;
      *) echo "Please answer y or n." ;;
    esac
  done
}

is_windows_host() {
  [[ "${OSTYPE:-}" == msys* || "${OSTYPE:-}" == cygwin* || "${OS:-}" == "Windows_NT" ]]
}

candidate_exists() {
  local py_cmd="$1"
  eval "$py_cmd -c \"import sys\"" >/dev/null 2>&1
}

pick_python_with_ensurepip() {
  local candidates=(
    "py -3.12"
    "./auto_text_to_voice/VieNeu-TTS/.venv-win/Scripts/python.exe"
    "./auto_text_to_voice/VieNeu-TTS/.venv/Scripts/python.exe"
    "py -3.11"
    "py -3.10"
    "py -3"
    "python"
    "python3"
  )
  local candidate
  for candidate in "${candidates[@]}"; do
    if eval "$candidate -c \"import ensurepip, sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)\"" >/dev/null 2>&1; then
      echo "$candidate"
      return 0
    fi
  done
  return 1
}

pick_python_exact_minor() {
  local wanted="$1"
  local candidates=(
    "py -${wanted}"
    "python${wanted}"
    "python"
    "python3"
  )
  local candidate
  for candidate in "${candidates[@]}"; do
    if eval "$candidate -c \"import ensurepip, sys; raise SystemExit(0 if f'{sys.version_info.major}.{sys.version_info.minor}' == '${wanted}' else 1)\"" >/dev/null 2>&1; then
      echo "$candidate"
      return 0
    fi
  done
  return 1
}

python_version_tuple() {
  local py_cmd="$1"
  eval "$py_cmd -c \"import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')\""
}

python_executable() {
  local py_cmd="$1"
  eval "$py_cmd -c \"import sys; print(sys.executable)\"" 2>/dev/null || printf "%s" "$py_cmd"
}

install_python_312_windows() {
  if ! is_windows_host; then
    return 1
  fi
  if ! command -v winget >/dev/null 2>&1 && ! command -v winget.exe >/dev/null 2>&1; then
    echo "[ERROR] Python 3.12 not found and winget is unavailable for automatic install."
    return 1
  fi
  local winget_cmd="winget"
  if ! command -v winget >/dev/null 2>&1 && command -v winget.exe >/dev/null 2>&1; then
    winget_cmd="winget.exe"
  fi
  if ! ask_yes_no "Python 3.12 is required for Windows TTS. Install Python 3.12 with winget now?" "y"; then
    return 1
  fi
  if ! run_quiet "Install Python 3.12" "$winget_cmd" install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements; then
    echo "[ERROR] Failed to install Python 3.12 via winget."
    tail -n 80 "$SETUP_LOG" || true
    return 1
  fi
  hash -r 2>/dev/null || true
  return 0
}

runtime_inventory() {
  {
    echo "===== Runtime inventory ====="
    echo "OSTYPE=${OSTYPE:-}"
    echo "OS=${OS:-}"
    echo "PATH=$PATH"
    for candidate in "py -3.12" "py -3.11" "py -3.10" "py -3" "python" "python3"; do
      if candidate_exists "$candidate"; then
        local version exe torch_info
        version="$(python_version_tuple "$candidate" 2>/dev/null || true)"
        exe="$(python_executable "$candidate" 2>/dev/null || true)"
        torch_info="$(eval "$candidate - <<'PY'
try:
    import torch
    print(f'torch={torch.__version__}, cuda={torch.cuda.is_available()}, cuda_version={getattr(torch.version, 'cuda', None)}')
except Exception as exc:
    print(f'torch_missing={exc}')
PY" 2>/dev/null || true)"
        echo "Python candidate: $candidate | version=$version | exe=$exe | $torch_info"
      else
        echo "Python candidate: $candidate | not found"
      fi
    done
    if command -v nvidia-smi >/dev/null 2>&1; then
      echo "nvidia-smi: available"
      nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader 2>/dev/null || true
    else
      echo "nvidia-smi: not found"
    fi
    echo "============================="
  } >>"$SETUP_LOG"
}

http_ok() {
  local url="$1"
  if command -v curl >/dev/null 2>&1; then
    curl -fsS --max-time 2 "$url" >/dev/null 2>&1
    return $?
  fi
  return 1
}

is_9router_running() {
  if command -v powershell.exe >/dev/null 2>&1; then
    powershell.exe -NoProfile -ExecutionPolicy Bypass -Command '$items = @(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match "9router" }); if ($items.Count -gt 0) { exit 0 } else { exit 1 }' >/dev/null 2>&1
    return $?
  fi
  if command -v pgrep >/dev/null 2>&1; then
    pgrep -f "9router" >/dev/null 2>&1
    return $?
  fi
  return 1
}

short_vieneu_venv_dir() {
  if [[ -n "${SETUP_VIENEU_VENV_DIR:-}" ]]; then
    printf "%s" "$SETUP_VIENEU_VENV_DIR"
    return
  fi

  if [[ ("${OSTYPE:-}" == msys* || "${OSTYPE:-}" == cygwin* || "${OS:-}" == "Windows_NT") && -n "$(command -v cygpath || true)" ]]; then
    local repo_win repo_hash drive_letter drive_mount
    repo_win="$(cygpath -m "$(pwd)")"
    repo_hash="$(printf "%s" "$repo_win" | sha1sum | awk '{print substr($1,1,8)}')"
    drive_letter="${repo_win:0:1}"
    drive_mount="/${drive_letter,,}"
    printf "%s" "${drive_mount}/.vieneu-${repo_hash}"
    return
  fi

  printf "%s" "./auto_text_to_voice/VieNeu-TTS/.venv-win"
}

remove_vieneu_venv_path() {
  local path="$1"
  if [[ ! -e "$path" && ! -L "$path" ]]; then
    return 0
  fi

  if command -v powershell.exe >/dev/null 2>&1; then
    local path_win
    path_win="$(cygpath -w "$path" 2>/dev/null || printf "%s" "$path")"
    powershell.exe -NoProfile -ExecutionPolicy Bypass -Command \
      "Remove-Item -LiteralPath '\\?\$path_win' -Recurse -Force -ErrorAction SilentlyContinue" >>"$SETUP_LOG" 2>&1 || true
  fi

  rm -rf "$path"
}

ensure_vieneu_venv_link() {
  local link_dir="$1"
  local target_dir="$2"

  if [[ "$link_dir" == "$target_dir" ]]; then
    return 0
  fi

  if [[ -e "$link_dir" || -L "$link_dir" ]]; then
    if [[ -f "${link_dir}/Scripts/python.exe" || -f "${link_dir}/bin/python" ]]; then
      return 0
    fi
    remove_vieneu_venv_path "$link_dir"
  fi

  mkdir -p "$(dirname "$link_dir")"
  if command -v powershell.exe >/dev/null 2>&1; then
    local link_win target_win
    link_win="$(cygpath -w "$link_dir" 2>/dev/null || printf "%s" "$link_dir")"
    target_win="$(cygpath -w "$target_dir" 2>/dev/null || printf "%s" "$target_dir")"
    powershell.exe -NoProfile -ExecutionPolicy Bypass -Command \
      "New-Item -ItemType Junction -Path '$link_win' -Target '$target_win' -Force | Out-Null" >>"$SETUP_LOG" 2>&1 \
      && return 0
  fi

  ln -s "$target_dir" "$link_dir"
}

validate_vieneu_runtime() {
  local venv_py="$1"
  local tts_root="$2"
  local expected_device="${3:-auto}"
  if [[ ! -x "$venv_py" ]]; then
    return 1
  fi
  EXPECTED_TTS_DEVICE="$expected_device" "$venv_py" - <<'PY' >>"$SETUP_LOG" 2>&1
import os
import sys
sys.path.insert(0, os.path.join(os.getcwd(), "auto_text_to_voice", "VieNeu-TTS", "src"))
import numpy
import soundfile
import torch
import voxcpm
import vieneu
expected = os.environ.get("EXPECTED_TTS_DEVICE", "auto")
print("VieNeu runtime OK")
print("python=", sys.executable)
print("torch=", torch.__version__)
print("cuda_available=", torch.cuda.is_available())
print("cuda_version=", torch.version.cuda)
if expected == "cuda" and (not torch.cuda.is_available() or torch.version.cuda is None):
    raise SystemExit("CUDA torch is required for TTS but current torch cannot use CUDA.")
PY
}

validate_web_runtime() {
  local web_py="$1"
  if [[ ! -x "$web_py" ]]; then
    return 1
  fi
  "$web_py" - <<'PY' >>"$SETUP_LOG" 2>&1
import sys
import fastapi
import uvicorn
import httpx
import pydantic
import playwright
import imageio_ffmpeg
print("Web runtime OK")
print("python=", sys.executable)
PY
}

write_setup_validation_fixture() {
  local session_dir="./projects_workspace/projects/setup-validation/sessions/setup-validation-session"
  rm -rf "./projects_workspace/projects/setup-validation"
  mkdir -p "${session_dir}/tts_inputs"
  cat >"${session_dir}/session.json" <<'JSON'
{
  "project_id": "setup-validation",
  "session_id": "setup-validation-session",
  "name": "Setup validation",
  "status": "ready"
}
JSON
  cat >"${session_dir}/tts_inputs/text_0001.txt" <<'TXT'
Thien Dau de quoc Thanh Hon thon. Ngay hom nay la le thuc tinh vo hon hang nam.
TXT
}

validate_latest_setup_audio_benchmark() {
  "$WEB_PY" - <<'PY' >>"$SETUP_LOG" 2>&1
import audioop
import json
import math
import wave
from pathlib import Path

root = Path("benchmarks/setup_validation")
if not root.exists():
    raise SystemExit("Missing setup validation benchmark directory.")
runs = sorted((p for p in root.iterdir() if p.is_dir()), key=lambda p: p.stat().st_mtime)
if not runs:
    raise SystemExit("No setup validation benchmark runs found.")
latest = runs[-1]
report = json.loads((latest / "reports" / "benchmark.json").read_text(encoding="utf-8"))
if not report.get("success"):
    raise SystemExit("Setup validation benchmark did not succeed.")
config = report.get("config") or {}
if config.get("temperature") != 0.05 or config.get("postprocess") is not False:
    raise SystemExit(f"Unexpected benchmark quality config: {config}")
combined = latest / "output" / "combined.wav"
if not combined.exists():
    raise SystemExit(f"Missing combined WAV: {combined}")
with wave.open(str(combined), "rb") as wav:
    frames = wav.getnframes()
    rate = wav.getframerate()
    width = wav.getsampwidth()
    data = wav.readframes(frames)
duration = frames / rate if rate else 0
if duration < 1.0:
    raise SystemExit(f"Combined WAV is too short: {duration:.3f}s")
full_scale = (2 ** (8 * width - 1)) - 1
peak = audioop.max(data, width)
rms = audioop.rms(data, width)
peak_dbfs = 20 * math.log10(max(peak, 1) / full_scale)
rms_dbfs = 20 * math.log10(max(rms, 1) / full_scale)
print(f"Setup validation WAV OK: duration={duration:.3f}s peak={peak_dbfs:.2f}dBFS rms={rms_dbfs:.2f}dBFS")
if peak_dbfs > -0.5:
    raise SystemExit(f"Audio is too close to clipping: peak={peak_dbfs:.2f}dBFS")
if rms_dbfs > -8.0:
    raise SystemExit(f"Audio is unexpectedly hot: rms={rms_dbfs:.2f}dBFS")
PY
}

run_production_validation() {
  if [[ "${SETUP_SKIP_PRODUCTION_VALIDATE:-0}" == "1" ]]; then
    echo "SETUP_SKIP_PRODUCTION_VALIDATE=1, production validation skipped." >>"$SETUP_LOG"
    step_tick
    step_tick
    step_tick
    step_tick
    return 0
  fi
  if [[ "${SETUP_PRODUCTION_VALIDATE:-ask}" != "1" && "${CI:-0}" != "1" && "${SETUP_ASSUME_YES:-0}" != "1" ]]; then
    if ! ask_yes_no "Run a real one-chunk production TTS validation now? This verifies model/runtime/audio output." "y"; then
      echo "Production validation skipped by user." >>"$SETUP_LOG"
      step_tick
      step_tick
      step_tick
      step_tick
      return 0
    fi
  fi

  write_setup_validation_fixture
  run_quiet_or_fail "Compile production Python modules" "$WEB_PY" -m py_compile \
    auto_convert_text/pipeline/audio_cleaner.py \
    auto_convert_text/pipeline/simple_chunker.py \
    source_full/backend/pipeline_service.py \
    auto_text_to_voice/vieneu_worker.py \
    tools/benchmark_tts_pipeline.py
  run_quiet_or_fail "Run unit tests" "$WEB_PY" -m unittest discover -s tests
  run_quiet_or_fail "Run real TTS production validation" "$WEB_PY" tools/benchmark_tts_pipeline.py \
    --project-id setup-validation \
    --session-id setup-validation-session \
    --voice-profile su-review \
    --model-key voxcpm_vn \
    --temperature 0.05 \
    --top-k 80 \
    --tts-io-workers 2 \
    --inference-timesteps 8 \
    --no-cache \
    --text-limit 1 \
    --scenario setup_validation_tts \
    --artifact-root benchmarks/setup_validation
  if ! validate_latest_setup_audio_benchmark; then
    printf "\n%s %sProduction WAV validation failed.%s\n" "$(icon fail)" "$C_RED" "$C_RESET"
    echo "Recent log lines:"
    tail -n 80 "$SETUP_LOG" || true
    exit 1
  fi
  step_tick
}

ensure_9router() {
  if ! command -v 9router >/dev/null 2>&1; then
    if ! command -v npm >/dev/null 2>&1; then
      if is_windows_host && (command -v winget >/dev/null 2>&1 || command -v winget.exe >/dev/null 2>&1); then
        if ask_yes_no "npm is required for 9router but was not found. Install Node.js LTS with winget now?" "y"; then
          local winget_cmd="winget"
          if ! command -v winget >/dev/null 2>&1 && command -v winget.exe >/dev/null 2>&1; then
            winget_cmd="winget.exe"
          fi
          if ! run_quiet "Install Node.js LTS" "$winget_cmd" install -e --id OpenJS.NodeJS.LTS --accept-package-agreements --accept-source-agreements; then
            echo "[ERROR] Failed to install Node.js/npm via winget."
            tail -n 80 "$SETUP_LOG" || true
            exit 1
          fi
          hash -r 2>/dev/null || true
        fi
      fi
      if ! command -v npm >/dev/null 2>&1; then
        echo "[ERROR] npm is required to install 9router. Install Node.js/npm, then rerun setup.sh."
        exit 1
      fi
    fi
    if ! ask_yes_no "9router is missing. Install it globally with npm now?" "y"; then
      echo "[ERROR] 9router install declined."
      exit 1
    fi
    if ! run_quiet "Install 9router" npm install -g 9router; then
      echo "[ERROR] Failed to install 9router via npm install -g 9router."
      tail -n 80 "$SETUP_LOG" || true
      exit 1
    fi
    hash -r 2>/dev/null || true
    if ! command -v 9router >/dev/null 2>&1; then
      echo "[ERROR] 9router installed, but the 9router command is not available in PATH."
      echo "[HINT] Reopen Git Bash/terminal or add npm global bin to PATH, then rerun setup.sh."
      exit 1
    fi
  fi

  if http_ok "http://127.0.0.1:20128/v1/models"; then
    step_tick
    return
  fi
  if is_9router_running; then
    echo "9router process is already running." >>"$SETUP_LOG"
    step_tick
    return
  fi

  echo "Starting 9router..." >>"$SETUP_LOG"
  nohup 9router >>"$LOG_DIR/9router.log" 2>&1 &
  sleep 3
  if ! http_ok "http://127.0.0.1:20128/v1/models"; then
    echo "[WARN] 9router was started but http://127.0.0.1:20128/v1/models is not responding yet." >>"$SETUP_LOG"
  fi
  step_tick
}

find_chrome_executable() {
  if [[ -n "${CHROME_PATH:-}" && -f "${CHROME_PATH:-}" ]]; then
    printf "%s" "$CHROME_PATH"
    return 0
  fi
  local candidates=(
    "/c/Program Files/Google/Chrome/Application/chrome.exe"
    "/c/Program Files (x86)/Google/Chrome/Application/chrome.exe"
    "${LOCALAPPDATA:-}/Google/Chrome/Application/chrome.exe"
  )
  local candidate
  for candidate in "${candidates[@]}"; do
    if [[ -f "$candidate" ]]; then
      printf "%s" "$candidate"
      return 0
    fi
  done
  if command -v chrome.exe >/dev/null 2>&1; then
    command -v chrome.exe
    return 0
  fi
  if command -v google-chrome >/dev/null 2>&1; then
    command -v google-chrome
    return 0
  fi
  return 1
}

devtools_new_tab() {
  local url="$1"
  local encoded="$url"
  if [[ -n "${WEB_PY:-}" && -x "${WEB_PY:-}" ]]; then
    encoded="$("$WEB_PY" -c "import sys, urllib.parse; print(urllib.parse.quote(sys.argv[1], safe=''))" "$url" 2>/dev/null || printf "%s" "$url")"
  fi
  if command -v curl >/dev/null 2>&1; then
    curl -fsS -X PUT --max-time 3 "http://127.0.0.1:9222/json/new?${encoded}" >/dev/null 2>&1 \
      || curl -fsS --max-time 3 "http://127.0.0.1:9222/json/new?${encoded}" >/dev/null 2>&1 \
      || true
  fi
}

ensure_default_chrome_tabs() {
  local cdp_url="http://127.0.0.1:9222/json/version"
  local gpt_url="https://chatgpt.com/?model=gpt-4o"
  local story_url="https://apptruyenchu.pro"

  if http_ok "$cdp_url"; then
    devtools_new_tab "$gpt_url"
    devtools_new_tab "$story_url"
    step_tick
    return
  fi

  local chrome
  chrome="$(find_chrome_executable || true)"
  if [[ -z "$chrome" ]]; then
    echo "[WARN] Chrome not found. Set CHROME_PATH or install Google Chrome to auto-open GPT/story tabs." >>"$SETUP_LOG"
    step_tick
    return
  fi

  local profile_dir="D:/chrome-gpt-profile-pool/port_9222"
  mkdir -p "$profile_dir"
  "$chrome" \
    --remote-debugging-port=9222 \
    --user-data-dir="$profile_dir" \
    "$gpt_url" \
    "$story_url" >>"$SETUP_LOG" 2>&1 &
  sleep 3
  if ! http_ok "$cdp_url"; then
    echo "[WARN] Chrome was opened but remote debugging port 9222 is not responding yet." >>"$SETUP_LOG"
  fi
  step_tick
}

ensure_vieneu_runtime() {
  local tts_root="./auto_text_to_voice/VieNeu-TTS"
  local compat_venv_dir="${tts_root}/.venv-win"
  local venv_dir
  venv_dir="$(short_vieneu_venv_dir)"
  local venv_py="${venv_dir}/Scripts/python.exe"
  local llama_wheel_url="https://github.com/pnnbao97/VieNeu-TTS/releases/download/wheels-v0.3.16/llama_cpp_python-0.3.16-cp312-cp312-win_amd64.whl"
  local torch_index="https://download.pytorch.org/whl/cpu"
  local expect_device="cpu"
  local requested_device="${SETUP_TTS_DEVICE:-auto}"
  local system_py_version

  system_py_version="$(python_version_tuple "$TTS_SYSTEM_PYTHON")"
  if is_windows_host; then
    if [[ "$system_py_version" != "3.12" ]]; then
      echo "[ERROR] Windows TTS setup needs Python 3.12 for the prebuilt llama-cpp/VoxCPM wheels, got ${system_py_version} from ${TTS_SYSTEM_PYTHON}."
      exit 1
    fi
  fi

  if [[ ! -f "$venv_py" && -f "${tts_root}/.venv/bin/python" ]]; then
    venv_dir="${tts_root}/.venv"
    venv_py="${venv_dir}/bin/python"
  fi

  if [[ "$requested_device" == "cuda" ]] && command -v nvidia-smi >/dev/null 2>&1; then
    torch_index="https://download.pytorch.org/whl/cu128"
    expect_device="cuda"
  elif [[ "$requested_device" == "auto" ]] && command -v nvidia-smi >/dev/null 2>&1; then
    torch_index="https://download.pytorch.org/whl/cu128"
    expect_device="cuda"
  elif [[ "$requested_device" == "cuda" ]]; then
    echo "[ERROR] SETUP_TTS_DEVICE=cuda but nvidia-smi is not available. Install NVIDIA driver/CUDA runtime first."
    exit 1
  fi

  if [[ -x "$venv_py" ]] && is_windows_host; then
    local venv_py_version
    venv_py_version="$("$venv_py" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || true)"
    if [[ "$venv_py_version" != "3.12" ]]; then
      echo "[WARN] Existing VieNeu runtime uses Python ${venv_py_version:-unknown}, but Windows TTS requires Python 3.12: $venv_py" >>"$SETUP_LOG"
      if ! ask_yes_no "VieNeu/TTS venv was built with Python ${venv_py_version:-unknown}. Recreate it with Python 3.12 now?" "y"; then
        echo "[ERROR] VieNeu/TTS runtime recreate declined."
        exit 1
      fi
      remove_vieneu_venv_path "$venv_dir"
      remove_vieneu_venv_path "$compat_venv_dir"
      venv_py="${venv_dir}/Scripts/python.exe"
    fi
  fi

  if [[ -x "$venv_py" ]] && validate_vieneu_runtime "$venv_py" "$tts_root" "$expect_device"; then
    echo "Reusing valid VieNeu runtime: $venv_py" >>"$SETUP_LOG"
    PIPELINE_PY="$venv_py"
    return 0
  fi

  if [[ -x "$venv_py" ]]; then
    echo "[WARN] Existing VieNeu runtime is missing packages or failed validation: $venv_py" >>"$SETUP_LOG"
    if ! ask_yes_no "VieNeu/TTS runtime exists but is incomplete. Repair/install dependencies now?" "y"; then
      echo "[ERROR] VieNeu/TTS runtime repair declined."
      exit 1
    fi
  fi

  if [[ ! -x "$venv_py" ]]; then
    if ! ask_yes_no "VieNeu/TTS Python environment is missing. Create and install it now?" "y"; then
      echo "[ERROR] VieNeu/TTS runtime install declined."
      exit 1
    fi
    echo "  $(icon run) Creating VieNeu virtual environment..."
    remove_vieneu_venv_path "$venv_dir"
    remove_vieneu_venv_path "$compat_venv_dir"
    run_quiet_or_fail "Create VieNeu venv" bash -lc "$TTS_SYSTEM_PYTHON -m venv \"$venv_dir\""
    ensure_vieneu_venv_link "$compat_venv_dir" "$venv_dir"
    if [[ -f "${venv_dir}/Scripts/python.exe" ]]; then
      venv_py="${venv_dir}/Scripts/python.exe"
    else
      venv_py="${venv_dir}/bin/python"
    fi
  elif [[ "$venv_dir" != "$compat_venv_dir" ]]; then
    ensure_vieneu_venv_link "$compat_venv_dir" "$venv_dir"
  fi

  if [[ ! -x "$venv_py" ]]; then
    echo "[ERROR] Failed to create VieNeu runtime at $venv_py"
    exit 1
  fi

  echo "Runtime target device: ${expect_device}" >>"$SETUP_LOG"
  run_quiet_or_fail "Upgrade VieNeu pip toolchain" "$venv_py" -m pip install --upgrade pip "setuptools<82" wheel --progress-bar on

  # Prefer prebuilt llama-cpp wheel on Windows to avoid requiring local C/C++ build toolchain.
  if [[ "$venv_py" == *"/Scripts/python.exe" ]]; then
    if ! run_quiet "Install prebuilt llama-cpp wheel" "$venv_py" -m pip install "$llama_wheel_url" --progress-bar on; then
      echo "[WARN] Prebuilt llama-cpp wheel install failed; fallback to regular dependency resolution." >>"$SETUP_LOG"
    fi
  fi

  run_quiet_or_fail "Install VieNeu minimal deps" "$venv_py" -m pip install sea-g2p onnxruntime requests numpy soundfile PyYAML librosa tqdm perth voxcpm transformers accelerate huggingface_hub --progress-bar on
  run_quiet_or_fail "Install VieNeu package" "$venv_py" -m pip install -e "$tts_root" --no-deps --progress-bar on
  if [[ "$expect_device" == "cuda" ]]; then
    run_quiet_or_fail "Install CUDA torch + torchaudio" "$venv_py" -m pip install --force-reinstall --index-url "$torch_index" torch torchaudio --progress-bar on
  else
    run_quiet_or_fail "Install torch + torchaudio" "$venv_py" -m pip install --index-url "$torch_index" torch torchaudio --progress-bar on
  fi
  if [[ "$expect_device" == "cuda" ]]; then
    run_quiet_or_fail "Install CUDA runtime deps" "$venv_py" -m pip install --upgrade onnxruntime-gpu neucodec transformers accelerate --progress-bar on
  fi

  if ! validate_vieneu_runtime "$venv_py" "$tts_root" "$expect_device"; then
    echo "[ERROR] VieNeu runtime validation failed."
    tail -n 80 "$SETUP_LOG" || true
    exit 1
  fi

  PIPELINE_PY="$venv_py"
}

pick_port() {
  local ports=(8080 8081 8082 8090)
  local p
  for p in "${ports[@]}"; do
    if ! "$WEB_PY" - <<PY >/dev/null 2>&1
import socket
s = socket.socket()
try:
    s.bind(("127.0.0.1", ${p}))
except OSError:
    raise SystemExit(1)
finally:
    s.close()
raise SystemExit(0)
PY
    then
      continue
    fi
    echo "$p"
    return 0
  done
  return 1
}

print_header_clean
step "Inspect OS/Python/GPU runtimes" 1
runtime_inventory
step_tick

WEB_SYSTEM_PYTHON="$(pick_python_with_ensurepip || true)"
if [[ -z "$WEB_SYSTEM_PYTHON" ]]; then
  if is_windows_host && install_python_312_windows; then
    WEB_SYSTEM_PYTHON="$(pick_python_with_ensurepip || true)"
  fi
fi
if [[ -z "$WEB_SYSTEM_PYTHON" ]]; then
  echo "[ERROR] Python 3.10+ with ensurepip is not available (tried: py -3.12, py -3.11, py -3.10, py -3, python, python3)."
  echo "[HINT] Install Python 3.10+ or allow setup to install Python 3.12 on Windows."
  exit 1
fi

TTS_SYSTEM_PYTHON=""
if is_windows_host; then
  TTS_SYSTEM_PYTHON="$(pick_python_exact_minor "3.12" || true)"
  if [[ -z "$TTS_SYSTEM_PYTHON" ]] && install_python_312_windows; then
    TTS_SYSTEM_PYTHON="$(pick_python_exact_minor "3.12" || true)"
  fi
else
  TTS_SYSTEM_PYTHON="$(pick_python_with_ensurepip || true)"
fi
if [[ -z "$TTS_SYSTEM_PYTHON" ]]; then
  echo "[ERROR] Cannot find a suitable Python for TTS runtime."
  if is_windows_host; then
    echo "[HINT] Windows TTS needs Python 3.12. Install it, or answer y when setup asks to install via winget."
  fi
  exit 1
fi

step "Select Python runtime" 1
{
  echo "Selected WEB_SYSTEM_PYTHON=$WEB_SYSTEM_PYTHON"
  echo "Selected WEB executable=$(python_executable "$WEB_SYSTEM_PYTHON")"
  echo "Selected WEB version=$(python_version_tuple "$WEB_SYSTEM_PYTHON")"
  echo "Selected TTS_SYSTEM_PYTHON=$TTS_SYSTEM_PYTHON"
  echo "Selected TTS executable=$(python_executable "$TTS_SYSTEM_PYTHON")"
  echo "Selected TTS version=$(python_version_tuple "$TTS_SYSTEM_PYTHON")"
} >>"$SETUP_LOG"
step_tick

recreate_venv() {
  rm -rf .venv
  eval "$WEB_SYSTEM_PYTHON -m venv .venv"
}

if [[ ! -d ".venv" ]]; then
  step "Create web virtual environment" 1
  if ! ask_yes_no "Web Python environment .venv is missing. Create it now?" "y"; then
    echo "[ERROR] Web runtime creation declined."
    exit 1
  fi
  recreate_venv
  step_tick
else
  step "Validate web virtual environment" 1
  step_tick
fi

if [[ -f ".venv/Scripts/python.exe" ]]; then
  WEB_PY=".venv/Scripts/python.exe"
else
  WEB_PY=".venv/bin/python"
fi

if [[ ! -x "$WEB_PY" ]]; then
  echo "  $(icon run) Existing .venv invalid, recreating..."
  if ! ask_yes_no "Existing web .venv is invalid. Recreate it now?" "y"; then
    echo "[ERROR] Web runtime recreate declined."
    exit 1
  fi
  recreate_venv
  if [[ -f ".venv/Scripts/python.exe" ]]; then
    WEB_PY=".venv/Scripts/python.exe"
  else
    WEB_PY=".venv/bin/python"
  fi
fi

if validate_web_runtime "$WEB_PY"; then
  step "Validate web dependencies" 1
  echo "Reusing valid web runtime: $WEB_PY" >>"$SETUP_LOG"
  step_tick
else
  step "Install web dependencies" 3
  if ! ask_yes_no "Web dependencies are missing or incomplete. Install them into .venv now?" "y"; then
    echo "[ERROR] Web dependency install declined."
    exit 1
  fi
  run_quiet_or_fail "Upgrade web pip" "$WEB_PY" -m pip install --upgrade pip --progress-bar on
  run_quiet_or_fail "Install web requirements" "$WEB_PY" -m pip install -r source_full/requirements.txt --progress-bar on
  run_quiet_or_warn "Install Playwright Chromium" "$WEB_PY" -m playwright install chromium
fi

step "Ensure 9router runtime" 1
ensure_9router

step "Open default Chrome tabs" 1
ensure_default_chrome_tabs

PIPELINE_PY=""
TTS_TASKS=5
if command -v nvidia-smi >/dev/null 2>&1; then
  TTS_TASKS=$((TTS_TASKS + 1))
fi
if [[ ! -x "./auto_text_to_voice/VieNeu-TTS/.venv-win/Scripts/python.exe" ]]; then
  TTS_TASKS=$((TTS_TASKS + 1))
fi
step "Install and validate TTS runtime" "$TTS_TASKS"
ensure_vieneu_runtime
step_tick

step "Prewarm TTS model" 1
run_quiet_or_fail "Prewarm TTS model" "$WEB_PY" -c "from pathlib import Path; from source_full.backend.pipeline_service import AudioPipelineService; s=AudioPipelineService(Path('.')); r=s.prewarm(); import sys; sys.exit(0 if r.get('ok') else 1)"

step "Run production validation" 4
run_production_validation

if [[ "${SETUP_INSTALL_ONLY:-0}" == "1" ]]; then
  echo "SETUP_INSTALL_ONLY=1, setup completed without starting web controller." >>"$SETUP_LOG"
  printf "\n%s Setup install/validation completed without starting web controller.\n" "$(icon ok)"
  printf "%s Log: %s\n\n" "$(icon info)" "$SETUP_LOG"
  exit 0
fi

step "Pick server port" 1
PORT="$(pick_port || true)"
if [[ -z "$PORT" ]]; then
  echo "[ERROR] Cannot find an available port (tried: 8080, 8081, 8082, 8090)."
  exit 1
fi
echo "Selected port: $PORT" >>"$SETUP_LOG"
step_tick

step "Start web controller" 1
echo "URL: http://localhost:${PORT}" >>"$SETUP_LOG"
echo "Full logs: $SETUP_LOG" >>"$SETUP_LOG"
step_tick
printf "\n%s URL: %shttp://localhost:%s%s\n" "$(icon rocket)" "$C_BOLD" "$PORT" "$C_RESET"
printf "%s Log: %s\n\n" "$(icon info)" "$SETUP_LOG"
PORT="$PORT" "$WEB_PY" source_full/run_web.py
