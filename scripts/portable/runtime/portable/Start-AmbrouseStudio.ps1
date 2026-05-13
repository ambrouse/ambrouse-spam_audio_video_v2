param(
  [int]$StudioPort = 8080,
  [int]$BridgePort = 8008
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root "runtime\python\python.exe"
$NodeDir = Join-Path $Root "runtime\node"
$Wheelhouse = Join-Path $Root "wheelhouse"

function Step($Text) {
  Write-Host ""
  Write-Host "[ambrouse] $Text" -ForegroundColor Cyan
}

function Require-File($Path, $Hint) {
  if (!(Test-Path $Path)) {
    throw "$Hint Missing: $Path"
  }
}

function PipInstall($VenvPython, [string[]]$Args) {
  $pipArgs = @("-m", "pip", "install")
  if (Test-Path $Wheelhouse) {
    $pipArgs += @("--find-links", $Wheelhouse)
  }
  $pipArgs += $Args
  & $VenvPython @pipArgs
  if ($LASTEXITCODE -ne 0) { throw "pip install failed: $($Args -join ' ')" }
}

function Ensure-Venv($VenvDir) {
  $VenvPython = Join-Path $VenvDir "Scripts\python.exe"
  if (!(Test-Path $VenvPython)) {
    & $Python -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) { throw "venv create failed: $VenvDir" }
  }
  return $VenvPython
}

Require-File $Python "Portable Python runtime is not present."
$env:PATH = "$NodeDir;$Root\runtime\python;$env:PATH"
$env:PORT = "$StudioPort"
$env:GEMINI_API_PORT = "$BridgePort"
$env:BRIDGE_BASE_URL = "http://127.0.0.1:$BridgePort"
$env:SETUP_TTS_DEVICE = "cuda"
$env:SPAM_TTS_DEVICE = "cuda"
$env:VIDEO_ENCODER = "auto"
$env:VIDEO_RENDER_WORKERS = "6"
$env:VIDEO_BRIDGE_BATCH_SIZE = "24"
$env:CHAT_BRIDGE_DISCOVERY_PORTS = "9222,9223,9224"
$env:CHAT_BRIDGE_MAX_BATCH_PROMPTS = "24"

Step "Checking NVIDIA GPU"
$nvidia = Get-Command nvidia-smi -ErrorAction SilentlyContinue
if ($nvidia) {
  & nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader,nounits
} else {
  Write-Host "[ambrouse][warn] nvidia-smi not found. CUDA/NVENC runtime will not be ready." -ForegroundColor Yellow
}

Step "Preparing web runtime"
$WebVenvPython = Ensure-Venv (Join-Path $Root "spam_audio_video\.venv")
PipInstall $WebVenvPython @("-r", (Join-Path $Root "spam_audio_video\source_full\requirements.txt"))

Step "Preparing bridge runtime"
$BridgeVenvPython = Ensure-Venv (Join-Path $Root "toll-brouser-gpt-gemini\.venv")
PipInstall $BridgeVenvPython @("-e", (Join-Path $Root "toll-brouser-gpt-gemini"))
PipInstall $BridgeVenvPython @("fastapi", "uvicorn")

Step "Preparing CUDA TTS runtime"
$TtsRoot = Join-Path $Root "spam_audio_video\auto_text_to_voice\VieNeu-TTS"
$TtsVenvPython = Ensure-Venv (Join-Path $TtsRoot ".venv-win")
PipInstall $TtsVenvPython @("--upgrade", "pip", "setuptools<82", "wheel")
PipInstall $TtsVenvPython @("sea-g2p", "onnxruntime", "requests", "numpy", "soundfile", "PyYAML", "librosa", "tqdm", "perth", "voxcpm", "transformers", "accelerate", "huggingface_hub")
PipInstall $TtsVenvPython @("-e", $TtsRoot, "--no-deps")
& $TtsVenvPython -m pip install --force-reinstall --index-url "https://download.pytorch.org/whl/cu128" torch torchaudio
if ($LASTEXITCODE -ne 0) { throw "CUDA torch install failed." }
PipInstall $TtsVenvPython @("--upgrade", "onnxruntime-gpu", "neucodec", "transformers", "accelerate")

Step "Starting browser bridge"
$BridgeScript = Join-Path $Root "toll-brouser-gpt-gemini\examples\apps\gemini-use\server.py"
Start-Process -FilePath $BridgeVenvPython -ArgumentList "`"$BridgeScript`"" -WorkingDirectory (Join-Path $Root "toll-brouser-gpt-gemini") -WindowStyle Minimized
Start-Sleep -Seconds 3

Step "Starting Story Pipeline Studio"
$StudioScript = Join-Path $Root "spam_audio_video\source_full\run_web.py"
Write-Host "[ambrouse] Open: http://127.0.0.1:$StudioPort"
& $WebVenvPython $StudioScript
