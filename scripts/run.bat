@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0.."
set PYTHONPATH=%CD%\src
set PYTHONUTF8=1
".venv\Scripts\python.exe" -m mqwheel.main %*
endlocal
