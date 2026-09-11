@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if not exist ".venv\Scripts\pythonw.exe" (
  echo Echo is not set up yet. Create the virtual environment first:
  echo   python -m venv .venv
  echo   .venv\Scripts\activate
  echo   pip install -r requirements.txt
  echo.
  pause
  exit /b 1
)

REM pythonw keeps Echo in the tray with no console window.
REM If Echo is already running, this process asks it to show, then exits.
start "" ".venv\Scripts\pythonw.exe" "src\main.py"
