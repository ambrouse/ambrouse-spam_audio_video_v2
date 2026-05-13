$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root "runtime\python\python.exe"
$TtsRoot = Join-Path $Root "spam_audio_video\auto_text_to_voice\VieNeu-TTS"
$TtsVenv = Join-Path $TtsRoot ".venv-win"
$TtsPython = Join-Path $TtsVenv "Scripts\python.exe"

if (!(Test-Path $Python)) {
  throw "Portable Python missing: $Python"
}

if (!(Test-Path $TtsPython)) {
  & $Python -m venv $TtsVenv
  if ($LASTEXITCODE -ne 0) { throw "Failed to create TTS venv." }
}

& $TtsPython -m pip install --upgrade "pip" "setuptools<82" "wheel"
& $TtsPython -m pip install --force-reinstall --index-url "https://download.pytorch.org/whl/cu128" torch torchaudio
& $TtsPython -m pip install --upgrade onnxruntime-gpu neucodec transformers accelerate
& $TtsPython -c "import torch; print('torch=', torch.__version__); print('cuda_available=', torch.cuda.is_available()); print('cuda_version=', torch.version.cuda)"
