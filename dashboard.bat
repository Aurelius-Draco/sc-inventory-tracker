@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Run setup.bat first.
  pause
  exit /b 1
)
echo The dashboard opens in your browser. Close this window to stop it.
.venv\Scripts\python tracker.py --dashboard
pause
