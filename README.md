# VoiceCal — Persian Voice to Google Calendar

VoiceCal is a local-first Telegram assistant that turns Persian voice messages into editable calendar events. It transcribes audio on your own computer with `whisper.cpp` and a Persian fine-tuned Whisper model, extracts event details, and only creates an event in Google Calendar after you confirm the preview.

## Features

- Local Persian speech-to-text using `whisper.cpp` (no paid speech API required).
- Telegram voice-message and text input.
- Persian date parsing and event-field extraction: title, date, time, duration, and reminder.
- Interactive clarification for missing or ambiguous fields.
- Editable event preview with explicit confirmation before writing to Google Calendar.
- Windows setup scripts and automated tests.

## How it works

```text
Telegram voice/text
        ↓
Local audio decoding + whisper.cpp
        ↓
Persian ASR correction
        ↓
Event slot extraction and date parsing
        ↓
Clarify missing fields
        ↓
Editable preview → user confirmation
        ↓
Google Calendar
```

## Requirements

- Windows x64 (the included setup scripts target Windows).
- Python 3.11 or 3.12 recommended.
- A Telegram bot token.
- Google Calendar OAuth credentials.
- Internet access during initial setup to download dependencies, the whisper.cpp executable, and the Persian model.

The speech recognition model and executable run locally after setup. The model download is approximately 148 MB.

## Quick start (Windows)

1. Clone the repository and enter the project directory.
2. Create your local environment configuration:

   ```powershell
   Copy-Item .env.example .env
   ```

3. Edit `.env` and set your Telegram bot token and allowed Telegram user ID.
4. Run the setup script:

   ```bat
   setup_windows.bat
   ```

   If you already have a Python environment and only need to set up speech recognition, use `setup_stt_windows.bat`.

5. Place your Google OAuth client file at `credentials.json` (never commit it).
6. Connect Google Calendar if you have not already:

   ```bat
   connect_google.bat
   ```

7. Start VoiceCal:

   ```bat
   run.bat
   ```

8. Send a voice message to your Telegram bot.

## Example Persian voice request

> موضوع طراحی اپلیکیشن، تاریخ سی شهریور، ساعت پانزده، مدت یک ساعت، یادآور ده دقیقه قبل

VoiceCal extracts the event details and presents a preview. Confirm the preview to create the event.

## Configuration

See `.env.example` for the available settings. Common speech-to-text options include:

```env
WHISPER_CPP_EXE=tools/whispercpp/whisper-cli.exe
WHISPER_CPP_MODEL=models/ggml-base-fa.bin
WHISPER_CPP_THREADS=4
WHISPER_CPP_BEAM_SIZE=5
WHISPER_CPP_BEST_OF=5
```

The default values should be sufficient for a first run. The model and executable are downloaded by the setup scripts and intentionally excluded from Git.

## Tests

Activate the project virtual environment, then run:

```powershell
pytest -q
```

## Repository layout

```text
voicecal_bot/       Application and Telegram bot modules
tests/              Unit tests
scripts/            Speech recognition download and test utilities
.env.example        Example configuration (contains no live secrets)
requirements.txt    Python dependencies
setup_windows.bat   Windows setup
run.bat             Run the bot
connect_google.bat  Google Calendar OAuth setup
```

## Security notes

- Never commit `.env`, `credentials.json`, Telegram bot tokens, or Google OAuth token files.
- Local runtime data is excluded from Git.
- Restrict the bot using `ALLOWED_TELEGRAM_USER_ID` so it is not available to arbitrary Telegram users.
- If a token is exposed, revoke it and create a replacement.

## Notes

- VoiceCal is designed to run on your computer; a VPS or WordPress installation is not required.
- Initial setup requires network access. Transcription runs locally after the model and executable have been downloaded.
- The included scripts are Windows-focused; other operating systems may require manual setup adjustments.
