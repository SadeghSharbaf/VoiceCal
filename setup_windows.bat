@echo off
cd /d "%~dp0"
python -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
if not exist .env copy .env.example .env
call setup_stt_windows.bat
if errorlevel 1 goto failed
echo.
echo Setup complete.
echo 1. Put TELEGRAM_BOT_TOKEN in .env
echo 2. Put credentials.json here and run connect_google.bat if needed
echo 3. Run run.bat
pause
exit /b 0
:failed
echo Setup stopped because Persian STT setup failed.
pause
exit /b 1
