@echo off
title SC Inventory Tracker
cd /d "%~dp0.."
if not exist .venv\Scripts\python.exe (
  echo Run Setup.bat in the tracker folder first.
  pause
  exit /b 1
)
.venv\Scripts\python tracker.py %*
pause
