from __future__ import annotations

from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from .models import EventDraft


SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


class GoogleAuthRequired(RuntimeError):
    pass


class GoogleCalendarService:
    def __init__(self, token_file: Path, calendar_id: str):
        self.token_file = token_file
        self.calendar_id = calendar_id

    def _credentials(self) -> Credentials:
        if not self.token_file.exists():
            raise GoogleAuthRequired(
                "Google Calendar is not connected. Run: python -m voicecal_bot.google_auth"
            )
        creds = Credentials.from_authorized_user_file(str(self.token_file), SCOPES)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            self.token_file.write_text(creds.to_json(), encoding="utf-8")
        if not creds.valid:
            raise GoogleAuthRequired(
                "Google token is invalid. Run: python -m voicecal_bot.google_auth"
            )
        return creds

    def is_connected(self) -> bool:
        try:
            self._credentials()
            return True
        except Exception:
            return False

    def create_event(self, draft: EventDraft) -> dict:
        creds = self._credentials()
        service = build("calendar", "v3", credentials=creds, cache_discovery=False)

        start = draft.start_datetime()
        end = draft.end_datetime()
        body = {
            "summary": draft.title,
            "start": {"dateTime": start.isoformat(), "timeZone": draft.timezone},
            "end": {"dateTime": end.isoformat(), "timeZone": draft.timezone},
            "reminders": {
                "useDefault": False,
                "overrides": [
                    {"method": "popup", "minutes": int(draft.reminder_minutes)}
                ],
            },
        }
        rule = draft.recurrence_rule()
        if rule:
            body["recurrence"] = [rule]

        return (
            service.events()
            .insert(calendarId=self.calendar_id, body=body)
            .execute()
        )
