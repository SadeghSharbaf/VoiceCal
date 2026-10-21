from __future__ import annotations

from dotenv import load_dotenv
from google_auth_oauthlib.flow import InstalledAppFlow

from .calendar_service import SCOPES
from .config import Settings


def main() -> None:
    load_dotenv()
    settings = Settings.load(require_telegram_token=False)
    if not settings.google_credentials_file.exists():
        raise SystemExit(
            f"Missing {settings.google_credentials_file}. Download the Desktop OAuth client JSON from Google Cloud and save it with this name."
        )

    flow = InstalledAppFlow.from_client_secrets_file(
        str(settings.google_credentials_file), SCOPES
    )
    creds = flow.run_local_server(port=0)
    settings.google_token_file.parent.mkdir(parents=True, exist_ok=True)
    settings.google_token_file.write_text(creds.to_json(), encoding="utf-8")
    print(f"Google Calendar connected. Token saved to: {settings.google_token_file}")


if __name__ == "__main__":
    main()
