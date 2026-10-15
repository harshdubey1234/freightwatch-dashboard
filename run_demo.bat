@echo off
cd /d "%~dp0"
python -m freightwatch run
if errorlevel 1 (
  echo Install Python 3.10 or newer and ensure Python is on PATH.
  pause
  exit /b 1
)
start "" "results\dashboard.html"
