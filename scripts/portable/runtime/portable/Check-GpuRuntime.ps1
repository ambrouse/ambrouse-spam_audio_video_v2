$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$TtsPython = Join-Path $Root "spam_audio_video\auto_text_to_voice\VieNeu-TTS\.venv-win\Scripts\python.exe"
$WebPython = Join-Path $Root "spam_audio_video\.venv\Scripts\python.exe"

Write-Host "[ambrouse] NVIDIA"
if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
  & nvidia-smi --query-gpu=name,driver_version,memory.total,utilization.gpu --format=csv,noheader,nounits
} else {
  Write-Host "nvidia-smi: missing"
}

Write-Host ""
Write-Host "[ambrouse] TTS PyTorch"
if (Test-Path $TtsPython) {
  & $TtsPython -c "import json, torch; print(json.dumps({'torch': torch.__version__, 'cuda_available': bool(torch.cuda.is_available()), 'cuda_version': torch.version.cuda, 'device_count': torch.cuda.device_count() if torch.cuda.is_available() else 0}, ensure_ascii=False))"
} else {
  Write-Host "TTS venv missing: $TtsPython"
}

Write-Host ""
Write-Host "[ambrouse] Video encoder"
if (Test-Path $WebPython) {
  Push-Location (Join-Path $Root "spam_audio_video")
  try {
    $script = "from pathlib import Path; from auto_generate_video.pipeline import VideoPipeline; print(VideoPipeline(Path('.'))._resolve_video_encoder('auto'))"
    & $WebPython -c $script
  } finally {
    Pop-Location
  }
} else {
  Write-Host "Web venv missing: $WebPython"
}
