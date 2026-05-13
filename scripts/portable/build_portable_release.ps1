param(
  [string]$Version = "v0.1.1",
  [string]$PythonVersion = "3.12.7",
  [string]$NodeVersion = "22.13.1",
  [switch]$SkipRuntimeDownload
)

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$DistDir = Join-Path $RepoRoot "dist"
$BuildRoot = Join-Path $DistDir "_portable_build"
$ZipPath = Join-Path $DistDir "ambrouse-studio-$Version-win64.zip"
$CacheDir = Join-Path $RepoRoot ".release-cache"

function Step($Text) {
  Write-Host ""
  Write-Host "[portable] $Text" -ForegroundColor Cyan
}

function Download($Url, $Target) {
  if (Test-Path $Target) {
    return
  }
  Step "Downloading $Url"
  Invoke-WebRequest -Uri $Url -OutFile $Target
}

function Copy-Tree($Source, $Target, [string[]]$ExcludeDirs = @(), [string[]]$ExcludeFiles = @()) {
  New-Item -ItemType Directory -Force -Path $Target | Out-Null
  $xd = @()
  foreach ($item in $ExcludeDirs) { $xd += @("/XD", $item, (Join-Path $Source $item)) }
  $xf = @()
  foreach ($item in $ExcludeFiles) { $xf += @("/XF", $item) }
  robocopy $Source $Target /E /NFL /NDL /NJH /NJS /NP @xd @xf | Out-Null
  if ($LASTEXITCODE -ge 8) {
    throw "robocopy failed from $Source to $Target"
  }
}

Step "Preparing folders"
New-Item -ItemType Directory -Force -Path $DistDir, $CacheDir | Out-Null
if (Test-Path $BuildRoot) { cmd /c "rmdir /s /q `"$BuildRoot`"" | Out-Null }
if (Test-Path $ZipPath) { Remove-Item -Force $ZipPath }
New-Item -ItemType Directory -Force -Path $BuildRoot | Out-Null

Step "Copying source"
Copy-Tree (Join-Path $RepoRoot "spam_audio_video") (Join-Path $BuildRoot "spam_audio_video") `
  -ExcludeDirs @(".venv", ".venv-win", ".logs", "projects_workspace", "project_registry", "__pycache__", ".pytest_cache", "auto_text_to_voice\VieNeu-TTS\.venv-win", "auto_text_to_voice\VieNeu-TTS\.venv") `
  -ExcludeFiles @(".env", "*.pyc", "*.pyo", "*.log")
Copy-Tree (Join-Path $RepoRoot "toll-brouser-gpt-gemini") (Join-Path $BuildRoot "toll-brouser-gpt-gemini") `
  -ExcludeDirs @(".venv", ".git", ".ruff_cache", ".mypy_cache", ".pytest_cache", "generated-images", "temp", "tmp", "__pycache__") `
  -ExcludeFiles @(".env", "*.pyc", "*.pyo", "*.log")

Copy-Tree (Join-Path $RepoRoot "scripts\portable\runtime") $BuildRoot

Step "Writing default .env files"
Copy-Item (Join-Path $BuildRoot "spam_audio_video\.env.example") (Join-Path $BuildRoot "spam_audio_video\.env") -Force
Copy-Item (Join-Path $BuildRoot "toll-brouser-gpt-gemini\.env.example") (Join-Path $BuildRoot "toll-brouser-gpt-gemini\.env") -Force

if (!$SkipRuntimeDownload) {
  Step "Adding portable Python"
  $PythonNupkg = Join-Path $CacheDir "python.$PythonVersion.nupkg"
  $PythonZip = Join-Path $CacheDir "python.$PythonVersion.zip"
  $PythonExtract = Join-Path $CacheDir "python-$PythonVersion"
  Download "https://www.nuget.org/api/v2/package/python/$PythonVersion" $PythonNupkg
  if (!(Test-Path (Join-Path $PythonExtract "tools"))) {
    if (Test-Path $PythonExtract) { Remove-Item -Recurse -Force $PythonExtract }
    Copy-Item $PythonNupkg $PythonZip -Force
    Expand-Archive -Path $PythonZip -DestinationPath $PythonExtract
  }
  New-Item -ItemType Directory -Force -Path (Join-Path $BuildRoot "runtime\python") | Out-Null
  Copy-Tree (Join-Path $PythonExtract "tools") (Join-Path $BuildRoot "runtime\python")

  Step "Adding portable Node"
  $NodeZip = Join-Path $CacheDir "node-v$NodeVersion-win-x64.zip"
  $NodeExtract = Join-Path $CacheDir "node-v$NodeVersion-win-x64"
  Download "https://nodejs.org/dist/v$NodeVersion/node-v$NodeVersion-win-x64.zip" $NodeZip
  if (!(Test-Path $NodeExtract)) {
    Expand-Archive -Path $NodeZip -DestinationPath $CacheDir
  }
  New-Item -ItemType Directory -Force -Path (Join-Path $BuildRoot "runtime\node") | Out-Null
  Copy-Tree $NodeExtract (Join-Path $BuildRoot "runtime\node")
}

Step "Writing release manifest"
$manifest = [ordered]@{
  name = "ambrouse-studio"
  version = $Version
  target = "win64"
  python = $PythonVersion
  node = $NodeVersion
  entrypoint = "RUN.bat"
  notes = @(
    "Run RUN.bat to prepare local venvs and start bridge + studio.",
    "NVIDIA driver is still required for CUDA/NVENC.",
    "Login to Gemini/GPT in opened browser profiles on first use."
  )
}
$manifest | ConvertTo-Json -Depth 4 | Set-Content -Path (Join-Path $BuildRoot "release-manifest.json") -Encoding UTF8

Step "Compressing zip"
Compress-Archive -Path (Join-Path $BuildRoot "*") -DestinationPath $ZipPath -Force
Write-Host ""
Write-Host "[portable][ok] $ZipPath" -ForegroundColor Green
