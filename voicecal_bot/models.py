from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo


@dataclass
class EventDraft:
    title: str | None = None
    date_iso: str | None = None
    start_time: str | None = None
    ambiguous_time: str | None = None
    duration_minutes: int = 60
    reminder_minutes: int = 10
    recurrence: str | None = None  # daily | weekly | monthly | None
    timezone: str = "Asia/Tehran"
    source_text: str = ""
    # V1.5: if an anchor was heard but its value could not be parsed, keep that
    # optional field in the queue as well.  This lets us ask only for the broken
    # piece instead of making the user repeat the whole command.
    pending_fields: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EventDraft":
        # Backward compatible with V1.0-V1.4 SQLite rows.
        return cls(**data)

    def resolve_pending(self, field_name: str) -> None:
        self.pending_fields = [f for f in self.pending_fields if f != field_name]
        # Resolving a concrete time also resolves the AM/PM ambiguity.
        if field_name == "start_time":
            self.pending_fields = [f for f in self.pending_fields if f != "time_period"]
        if field_name == "time_period":
            self.pending_fields = [f for f in self.pending_fields if f != "start_time"]

    def next_missing_field(self) -> str | None:
        if self.pending_fields:
            return self.pending_fields[0]
        if not self.title:
            return "title"
        if not self.date_iso:
            return "date"
        if self.ambiguous_time and not self.start_time:
            return "time_period"
        if not self.start_time:
            return "start_time"
        return None

    def start_datetime(self) -> datetime:
        if not self.date_iso or not self.start_time:
            raise ValueError("Draft is incomplete")
        d = date.fromisoformat(self.date_iso)
        h, m = map(int, self.start_time.split(":"))
        return datetime.combine(d, time(h, m), tzinfo=ZoneInfo(self.timezone))

    def end_datetime(self) -> datetime:
        return self.start_datetime() + timedelta(minutes=self.duration_minutes)

    def recurrence_rule(self) -> str | None:
        mapping = {
            "daily": "RRULE:FREQ=DAILY",
            "weekly": "RRULE:FREQ=WEEKLY",
            "monthly": "RRULE:FREQ=MONTHLY",
        }
        return mapping.get(self.recurrence)
