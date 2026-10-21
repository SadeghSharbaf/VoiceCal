from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    allowed_telegram_user_id: int | None
    timezone: str
    google_calendar_id: str
    google_credentials_file: Path
    google_token_file: Path
    database_file: Path
    whisper_cpp_exe: Path
    whisper_cpp_model: Path
    whisper_cpp_threads: int
    whisper_cpp_beam_size: int
    whisper_cpp_best_of: int
    max_voice_seconds: int
    default_event_duration_minutes: int
    default_reminder_minutes: int

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    @classmethod
    def load(cls, require_telegram_token: bool = True) -> "Settings":
        load_dotenv()

        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        if require_telegram_token and not token:
            raise RuntimeError(
                "TELEGRAM_BOT_TOKEN is empty. Copy .env.example to .env and add your BotFather token."
            )

        allowed_raw = os.getenv("ALLOWED_TELEGRAM_USER_ID", "").strip()
        allowed = int(allowed_raw) if allowed_raw else None
        timezone = os.getenv("APP_TIMEZONE", "Asia/Tehran").strip()
        # Fail early for a typo in the timezone.
        ZoneInfo(timezone)

        settings = cls(
            telegram_bot_token=token,
            allowed_telegram_user_id=allowed,
            timezone=timezone,
            google_calendar_id=os.getenv("GOOGLE_CALENDAR_ID", "primary").strip(),
            google_credentials_file=Path(
                os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")
            ),
            google_token_file=Path(
                os.getenv("GOOGLE_TOKEN_FILE", "data/google_token.json")
            ),
            database_file=Path(os.getenv("DATABASE_FILE", "data/voicecal.db")),
            whisper_cpp_exe=Path(os.getenv("WHISPER_CPP_EXE", "tools/whispercpp/whisper-cli.exe")),
            whisper_cpp_model=Path(os.getenv("WHISPER_CPP_MODEL", "models/ggml-base-fa.bin")),
            whisper_cpp_threads=max(1, int(os.getenv("WHISPER_CPP_THREADS", "4"))),
            whisper_cpp_beam_size=max(1, int(os.getenv("WHISPER_CPP_BEAM_SIZE", "5"))),
            whisper_cpp_best_of=max(1, int(os.getenv("WHISPER_CPP_BEST_OF", "5"))),
            max_voice_seconds=max(1, int(os.getenv("MAX_VOICE_SECONDS", "90"))),
            default_event_duration_minutes=max(
                1, int(os.getenv("DEFAULT_EVENT_DURATION_MINUTES", "60"))
            ),
            default_reminder_minutes=max(
                0, int(os.getenv("DEFAULT_REMINDER_MINUTES", "10"))
            ),
        )

        settings.database_file.parent.mkdir(parents=True, exist_ok=True)
        settings.google_token_file.parent.mkdir(parents=True, exist_ok=True)
        return settings
