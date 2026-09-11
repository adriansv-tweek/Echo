@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "ROOT=%CD%"
set "PYTHONW=%ROOT%\.venv\Scripts\pythonw.exe"
set "SHORTCUT=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Echo.lnk"

if not exist "%PYTHONW%" (
  echo Echo virtual environment not found at:
  echo   %PYTHONW%
  echo.
  echo Create it first:
  echo   python -m venv .venv
  echo   .venv\Scripts\activate
  echo   pip install -r requirements.txt
  echo.
  pause
  exit /b 1
)

REM Creates a Start Menu shortcut only. Does not add Echo to Windows Startup.
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ws = New-Object -ComObject WScript.Shell;" ^
  "$s = $ws.CreateShortcut('%SHORTCUT%');" ^
  "$s.TargetPath = '%PYTHONW%';" ^
  "$s.Arguments = 'src\main.py';" ^
  "$s.WorkingDirectory = '%ROOT%';" ^
  "$s.WindowStyle = 1;" ^
  "$s.Description = 'Echo template helper';" ^
  "$s.Save();" ^
  "Write-Output 'Created Start Menu shortcut: %SHORTCUT%'"

if errorlevel 1 (
  echo Failed to create the Start Menu shortcut.
  pause
  exit /b 1
)

echo.
echo Echo is now available in Windows Search and the Start Menu.
echo It will not start automatically with Windows.
echo.
echo Launch: press Win, type Echo, press Enter.
echo Quit: right-click the Echo tray icon and choose Quit Echo.
echo.
pause
