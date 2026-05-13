@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0portable\Start-AmbrouseStudio.ps1"
endlocal
