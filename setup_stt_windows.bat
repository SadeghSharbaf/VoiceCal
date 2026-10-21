@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ================================================
echo VoiceCal V1.6.1 - Persian STT setup
echo whisper.cpp CPU + ggml-base-fa.bin (~148 MB)
echo ================================================
echo.

if not exist "tools\whispercpp" mkdir "tools\whispercpp"
if not exist "models" mkdir "models"

if exist "tools\whispercpp\whisper-cli.exe" goto model

echo [1/2] Downloading whisper.cpp Windows x64 CPU binary...
if not exist ".venv\Scripts\python.exe" (
  echo ERROR: Python virtual environment was not found.
  echo Run setup_windows.bat first.
  goto failed
)
".venv\Scripts\python.exe" "scripts\download_whispercpp.py"
if errorlevel 1 goto failed

:model
if exist "models\ggml-base-fa.bin" goto done

echo.
echo [2/2] Downloading Persian fine-tuned Whisper Base model (~148 MB)...
echo The download supports resume. If it stops, run this file again.
curl.exe -L --fail --retry 5 --retry-delay 2 -C - -o "models\ggml-base-fa.bin" "https://huggingface.co/SadeghK/whisper-base/resolve/main/ggml-base-fa.bin?download=true"
if errorlevel 1 goto failed

:done
echo.
if not exist "tools\whispercpp\whisper-cli.exe" goto failed
if not exist "models\ggml-base-fa.bin" goto failed

echo Persian STT setup complete.
echo Binary: tools\whispercpp\whisper-cli.exe
echo Model : models\ggml-base-fa.bin
echo.
pause
exit /b 0

:failed
echo.
echo STT setup failed. Run setup_stt_windows.bat again; downloads are resumable.
pause
exit /b 1
