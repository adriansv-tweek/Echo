@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "ROOT=%CD%"
set "ECHO_EXE=%ROOT%\dist\Echo\Echo.exe"
set "ECHO_DIR=%ROOT%\dist\Echo"
set "SHORTCUT=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Echo.lnk"

if not exist "%ECHO_EXE%" (
  echo Packaged Echo was not found at:
  echo   %ECHO_EXE%
  echo.
  echo Build it first with build_echo.bat, then run this again.
  echo.
  pause
  exit /b 1
)

REM Creates a Start Menu shortcut only. Does not add Echo to Windows Startup.
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ws = New-Object -ComObject WScript.Shell;" ^
  "$s = $ws.CreateShortcut('%SHORTCUT%');" ^
  "$s.TargetPath = '%ECHO_EXE%';" ^
  "$s.Arguments = '';" ^
  "$s.WorkingDirectory = '%ECHO_DIR%';" ^
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
