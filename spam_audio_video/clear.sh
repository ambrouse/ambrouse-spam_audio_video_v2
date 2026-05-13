#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORTS=(8080 8081 9222)

log() { printf '[clear] %s\n' "$*"; }

kill_ports_unix() {
  for p in "${PORTS[@]}"; do
    if command -v lsof >/dev/null 2>&1; then
      mapfile -t pids < <(lsof -ti tcp:"$p" -sTCP:LISTEN 2>/dev/null || true)
      if ((${#pids[@]})); then
        log "Killing port $p listeners: ${pids[*]}"
        kill -9 "${pids[@]}" 2>/dev/null || true
      fi
    elif command -v fuser >/dev/null 2>&1; then
      fuser -k "${p}/tcp" 2>/dev/null || true
    fi
  done
}

kill_repo_procs_unix() {
  if command -v pgrep >/dev/null 2>&1; then
    while IFS= read -r pid; do
      [[ -n "$pid" ]] || continue
      log "Killing repo process PID $pid"
      kill -9 "$pid" 2>/dev/null || true
    done < <(pgrep -f "$ROOT_DIR" || true)
  fi
}

clear_ram_linux_best_effort() {
  [[ "$(uname -s)" == "Linux" ]] || return 0
  if [[ "${CLEAR_DROP_CACHE:-0}" == "1" ]]; then
    if command -v sudo >/dev/null 2>&1; then
      log "Dropping Linux page cache (requires sudo)."
      sudo sh -c 'sync; echo 3 > /proc/sys/vm/drop_caches' || log "Skip drop_caches (no permission)."
    else
      log "sudo not found, skip drop_caches."
    fi
  else
    log "Skip RAM drop_caches (set CLEAR_DROP_CACHE=1 to enable)."
  fi
}

clear_vram_best_effort() {
  if command -v nvidia-smi >/dev/null 2>&1; then
    log "Checking NVIDIA compute processes..."
    mapfile -t gpu_pids < <(nvidia-smi --query-compute-apps=pid --format=csv,noheader,nounits 2>/dev/null | sed '/^\s*$/d' || true)
    if ((${#gpu_pids[@]})); then
      log "Killing GPU compute PIDs: ${gpu_pids[*]}"
      kill -9 "${gpu_pids[@]}" 2>/dev/null || true
    fi

    if [[ "${CLEAR_GPU_RESET:-0}" == "1" ]]; then
      log "Attempting nvidia-smi GPU reset (may fail on display GPU / insufficient permission)."
      nvidia-smi --gpu-reset || log "GPU reset not available in current environment."
    else
      log "Skip nvidia-smi --gpu-reset (set CLEAR_GPU_RESET=1 to enable)."
    fi
  else
    log "nvidia-smi not found, skip VRAM cleanup."
  fi
}

run_windows_clear_via_powershell() {
  local pwsh_bin=""
  if command -v powershell.exe >/dev/null 2>&1; then
    pwsh_bin="powershell.exe"
  elif command -v pwsh >/dev/null 2>&1; then
    pwsh_bin="pwsh"
  else
    return 1
  fi

  log "Running Windows cleanup via $pwsh_bin"
  "$pwsh_bin" -NoProfile -ExecutionPolicy Bypass -Command "
  \$ErrorActionPreference='SilentlyContinue';
  \$repo=(Resolve-Path '$ROOT_DIR').Path;
  \$ports=@(8080,8081,9222);
  \$owners=Get-NetTCPConnection -State Listen | Where-Object { \$_.LocalPort -in \$ports } | Select-Object -Expand OwningProcess -Unique;
  foreach(\$pid in \$owners){ try{ Stop-Process -Id \$pid -Force } catch{} }

  \$repoProcs=Get-CimInstance Win32_Process | Where-Object {
    (\$_.Name -match 'python|node|uvicorn') -and \$_.CommandLine -and (\$_.CommandLine -like \"*\$repo*\")
  };
  foreach(\$p in \$repoProcs){ try{ Stop-Process -Id \$p.ProcessId -Force } catch{} }

  \$chromeDebug=Get-CimInstance Win32_Process | Where-Object {
    \$_.Name -match '^chrome(\\.exe)?$' -and \$_.CommandLine -and (\$_.CommandLine -match '--remote-debugging-port=9222')
  };
  foreach(\$p in \$chromeDebug){ try{ Stop-Process -Id \$p.ProcessId -Force } catch{} }

  if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
    \$gpuPids = & nvidia-smi --query-compute-apps=pid --format=csv,noheader,nounits 2>\$null;
    foreach(\$line in \$gpuPids){
      \$t=\$line.Trim();
      if(\$t){ try{ Stop-Process -Id ([int]::Parse(\$t)) -Force } catch{} }
    }
    if (\$env:CLEAR_GPU_RESET -eq '1') {
      & nvidia-smi --gpu-reset 2>\$null | Out-Null;
    }
  }
  "
}

main() {
  log "Start cleanup in: $ROOT_DIR"

  if run_windows_clear_via_powershell; then
    log "Windows process cleanup completed."
  else
    kill_ports_unix
    kill_repo_procs_unix
  fi

  clear_vram_best_effort
  clear_ram_linux_best_effort

  log "Done."
}

main "$@"
