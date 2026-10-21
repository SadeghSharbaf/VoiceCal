@echo off
cd /d "%~dp0"
if "%~1"=="" (
  echo Drag a Telegram .ogg voice file onto this BAT file,
  echo or run: test_stt_windows.bat path\to\voice.ogg
  echo.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  echo Python environment is missing. Run setup_windows.bat first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" "scripts\test_stt.py" "%~1"
echo.
pause
