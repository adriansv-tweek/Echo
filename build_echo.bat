@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Echo virtual environment not found. Create it first:
  echo   python -m venv .venv
  echo   .venv\Scripts\activate
  echo   pip install -r requirements.txt
  echo   pip install -r requirements-build.txt
  exit /b 1
)

if not exist ".venv\Scripts\pyinstaller.exe" (
  echo Installing build tools into .venv ...
  ".venv\Scripts\python.exe" -m pip install -r requirements-build.txt
  if errorlevel 1 exit /b 1
)

".venv\Scripts\pyinstaller.exe" --noconfirm --clean Echo.spec
if errorlevel 1 exit /b 1

echo.
echo Built: %CD%\dist\Echo\Echo.exe
