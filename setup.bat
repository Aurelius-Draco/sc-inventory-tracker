@echo off
setlocal
cd /d "%~dp0"
echo SC Inventory Tracker - one-time setup
echo.

set PY=
py -3.13 -c "import sys" >nul 2>&1 && set PY=py -3.13
if not defined PY py -3.12 -c "import sys" >nul 2>&1 && set PY=py -3.12
if not defined PY python -c "import sys; assert (3,11)<=sys.version_info[:2]<=(3,13)" >nul 2>&1 && set PY=python

if not defined PY (
  echo Python 3.12 or 3.13 was not found.
  echo Install it by running this in a terminal, then run setup.bat again:
  echo.
  echo     winget install -e --id Python.Python.3.13
  echo.
  pause
  exit /b 1
)

echo Using: %PY%
%PY% -m venv .venv || goto fail
.venv\Scripts\python -m pip install --upgrade pip || goto fail
.venv\Scripts\python -m pip install -r requirements.txt || goto fail
echo.
echo Downloading and warming up the OCR model...
.venv\Scripts\python -c "from rapidocr import RapidOCR; RapidOCR(); print('OCR ready')" || goto fail
echo.
echo Setup complete. Use run.bat while playing, dashboard.bat to look things up.
pause
exit /b 0

:fail
echo.
echo Setup failed. Copy the error above into an issue on the project's GitHub page.
pause
exit /b 1
