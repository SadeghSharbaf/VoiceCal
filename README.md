# VoiceCal — Persian Voice-to-Google Calendar Assistant

VoiceCal turns Persian Telegram voice messages or text into structured Google Calendar events. Speech recognition runs locally on the user's computer with `whisper.cpp` and a Persian fine-tuned Whisper model. Before an event is created, VoiceCal presents an editable preview and waits for explicit confirmation.

## Highlights

- Persian voice-message and text input through Telegram.
- Local speech-to-text with `whisper.cpp` and `ggml-base-fa.bin` (approximately 148 MB).
- Extraction of event title, date, time, duration, and reminder.
- Follow-up prompts for unclear or missing fields rather than silently guessing.
- Editable event preview and explicit confirmation before writing to Google Calendar.
- Windows setup scripts, resumable model download, and automated tests.

## Workflow

```text
Telegram voice or text
        |
        v
Local audio decoding and whisper.cpp
        |
        v
Persian transcription and light correction
        |
        v
Event-field extraction and date parsing
        |
        v
Clarify missing or ambiguous fields
        |
        v
Editable event preview
        |
        v
User confirms
        |
        v
Google Calendar event
```

## Requirements

- Windows x64 (the included setup scripts are Windows-focused).
- Python 3.11 or 3.12 recommended.
- A Telegram bot token and your Telegram user ID.
- Google Calendar OAuth client credentials.
- Internet access for the initial dependency, executable, and model downloads.

After initial setup, transcription is performed locally. The default Persian model is approximately 148 MB; a large cloud speech API or CUDA installation is not required by the documented setup.

## Quick start (Windows)

1. Clone this repository and open its directory.
2. Create your local environment file:

   ```powershell
   Copy-Item .env.example .env
   ```

3. Add your Telegram bot token and restrict access with your Telegram user ID in `.env`.
4. Run the setup script:

   ```bat
   setup_windows.bat
   ```

   If the Python environment already exists and only speech recognition needs setup, run `setup_stt_windows.bat`.

5. Place your Google OAuth client file at `credentials.json`. Keep it out of version control.
6. Complete Google Calendar authorization when needed:

   ```bat
   connect_google.bat
   ```

7. Start the bot:

   ```bat
   run.bat
   ```

8. Send a Persian voice message or text request to your Telegram bot.

## Example request

```text
موضوع طراحی اپلیکیشن، تاریخ سی شهریور، ساعت پانزده،
مدت یک ساعت، یادآور ده دقیقه قبل
```

VoiceCal extracts the event details and shows a preview. Review and confirm it to create the calendar event.

## Configuration

Start with `.env.example`. The speech-to-text defaults use the local whisper.cpp executable and Persian model:

```env
WHISPER_CPP_EXE=tools/whispercpp/whisper-cli.exe
WHISPER_CPP_MODEL=models/ggml-base-fa.bin
WHISPER_CPP_THREADS=4
WHISPER_CPP_BEAM_SIZE=5
WHISPER_CPP_BEST_OF=5
```

Telegram configuration:

```env
TELEGRAM_BOT_TOKEN=your_bot_token
ALLOWED_TELEGRAM_USER_ID=your_telegram_user_id
```

Keep the bot private by setting `ALLOWED_TELEGRAM_USER_ID` to the intended account.

## Tests

Activate the project's virtual environment and run:

```powershell
pytest -q
```

## Security and privacy

- Never commit `.env`, `credentials.json`, Google token files, or Telegram bot tokens.
- Treat bot tokens and OAuth credentials like passwords.
- Restrict the Telegram bot to authorized user IDs.
- If a token is exposed, revoke it and issue a replacement.
- Review the Google OAuth scopes and permissions before authorizing the application.

## Notes

- VoiceCal is designed to run on a Windows computer; a VPS or WordPress installation is not required for the documented workflow.
- Initial setup requires network access to obtain dependencies, the whisper.cpp executable, and the model.
- Model files and downloaded binaries are intentionally kept out of Git.
- Speech recognition quality depends on recording quality, accent, background noise, and the selected model.

## License

No license is currently specified in this repository. All rights are reserved unless the project owner adds an explicit open-source license.
