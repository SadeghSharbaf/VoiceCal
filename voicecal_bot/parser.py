from __future__ import annotations

import re
from datetime import date, datetime, timedelta

from .jalali import gregorian_to_jalali, jalali_to_gregorian
from .models import EventDraft
from .text_utils import NUMBER_PHRASE_PATTERN, normalize_text, parse_number_phrase


JALALI_MONTHS = {
    "فروردین": 1,
    "اردیبهشت": 2,
    "خرداد": 3,
    "تیر": 4,
    "مرداد": 5,
    "شهریور": 6,
    "مهر": 7,
    "آبان": 8,
    "آذر": 9,
    "دی": 10,
    "بهمن": 11,
    "اسفند": 12,
}

GREGORIAN_MONTHS = {
    "ژانویه": 1,
    "فوریه": 2,
    "مارس": 3,
    "آوریل": 4,
    "اپریل": 4,
    "مه": 5,
    "می": 5,
    "ژوئن": 6,
    "جون": 6,
    "ژوئیه": 7,
    "جولای": 7,
    "اوت": 8,
    "آگوست": 8,
    "سپتامبر": 9,
    "اکتبر": 10,
    "نوامبر": 11,
    "دسامبر": 12,
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}

# Python weekday(): Monday=0 ... Sunday=6
WEEKDAYS = {
    "دوشنبه": 0,
    "سه شنبه": 1,
    "سه‌شنبه": 1,
    "چهارشنبه": 2,
    "پنجشنبه": 3,
    "پنج شنبه": 3,
    "جمعه": 4,
    "شنبه": 5,
    "یکشنبه": 6,
    "یک شنبه": 6,
}

# One shared number grammar is used for dates, times, durations, and reminders.
NUMBER_PHRASE = NUMBER_PHRASE_PATTERN
CLOCK_ATOM = rf"(?:\d{{1,2}}(?::\d{{1,2}})?|{NUMBER_PHRASE})"


class EventParser:
    def __init__(self, timezone: str, default_duration_minutes: int, default_reminder_minutes: int):
        self.timezone = timezone
        self.default_duration_minutes = default_duration_minutes
        self.default_reminder_minutes = default_reminder_minutes

    def parse(self, text: str, now: datetime) -> EventDraft:
        text = normalize_text(text)
        event_date = self.extract_date(text, now)
        start_time, ambiguous_time, range_duration = self.extract_time(text)
        explicit_duration = self.extract_duration(text)

        return EventDraft(
            title=self.extract_title(text),
            date_iso=event_date.isoformat() if event_date else None,
            start_time=start_time,
            ambiguous_time=ambiguous_time,
            duration_minutes=(
                explicit_duration
                if explicit_duration is not None
                else range_duration
                if range_duration is not None
                else self.default_duration_minutes
            ),
            reminder_minutes=(
                self.extract_reminder(text)
                if self.extract_reminder(text) is not None
                else self.default_reminder_minutes
            ),
            recurrence=self.extract_recurrence(text),
            timezone=self.timezone,
            source_text=text,
        )

    def patch_missing(self, draft: EventDraft, field: str, answer: str, now: datetime) -> bool:
        answer = normalize_text(answer)
        if field == "title":
            title = answer.strip(" .،")
            if not title:
                return False
            draft.title = title
            return True

        if field == "date":
            d = self.extract_date(answer, now)
            if not d:
                return False
            draft.date_iso = d.isoformat()
            return True

        if field == "start_time":
            start, ambiguous, _ = self.extract_time(answer, allow_bare_clock=True)
            if not start and not ambiguous:
                return False
            draft.start_time = start
            draft.ambiguous_time = ambiguous
            return True

        if field == "time_period":
            if not draft.ambiguous_time:
                return False
            hour, minute = map(int, draft.ambiguous_time.split(":"))
            if re.search(r"\b(?:صبح|صبحا|صبح‌ها)\b", answer):
                draft.start_time = f"{hour:02d}:{minute:02d}"
                draft.ambiguous_time = None
                return True
            if re.search(r"\b(?:عصر|شب|غروب|بعدازظهر|بعد از ظهر)\b", answer):
                if hour < 12:
                    hour += 12
                draft.start_time = f"{hour:02d}:{minute:02d}"
                draft.ambiguous_time = None
                return True
            return False

        if field == "duration":
            value = self.extract_duration(answer)
            if value is None:
                # During an edit flow the user may simply say "90 دقیقه".
                m = re.search(rf"({NUMBER_PHRASE})\s*(ساعت|دقیقه|دیقه|دقه)", answer)
                if m:
                    number = parse_number_phrase(m.group(1))
                    if number is not None:
                        value = int(number * (60 if m.group(2) == "ساعت" else 1))
            if value is None or value <= 0:
                return False
            draft.duration_minutes = value
            return True

        if field == "reminder":
            value = self.extract_reminder(answer)
            if value is None:
                if re.search(r"(?:بدون|نداشته|نذار|نزار).*(?:یادآور|یاداور)", answer):
                    value = 0
                else:
                    m = re.search(rf"({NUMBER_PHRASE})\s*(ساعت|دقیقه|دیقه|دقه)", answer)
                    if m:
                        number = parse_number_phrase(m.group(1))
                        if number is not None:
                            value = int(number * (60 if m.group(2) == "ساعت" else 1))
            if value is None or value < 0:
                return False
            draft.reminder_minutes = value
            return True

        return False

    def extract_title(self, text: str) -> str | None:
        # Most deterministic form: "با موضوع ..." or "با عنوان ..."
        marker = re.search(
            r"(?:با\s+موضوع|موضوع|با\s+عنوان|عنوان)\s+(.+?)(?=(?:\s+(?:یادآور|یاداور|یادآوری|یاداوری|به\s+مدت|بدون\s+تکرار|تکرار|هر\s+(?:روز|هفته|ماه)))|[.،]|$)",
            text,
            flags=re.IGNORECASE,
        )
        if marker:
            title = marker.group(1).strip(" .،")
            return title or None

        # Natural fallback: "برای خوندن شبکه وقت بذار"
        fallback = re.search(
            r"(?:برای|واسه)\s+(.+?)\s+(?:وقت|تایم)\s+(?:بذار|بزار|قرار\s+بده|ست\s+کن)",
            text,
        )
        if fallback:
            candidate = fallback.group(1).strip()
            # Don't accidentally use a date phrase as the title.
            if not any(month in candidate for month in (*JALALI_MONTHS.keys(), *GREGORIAN_MONTHS.keys())):
                return candidate
        return None

    def extract_date(self, text: str, now: datetime) -> date | None:
        text = normalize_text(text)
        today = now.date()

        # Explicit ISO-like Gregorian forms.
        m = re.search(r"\b(20\d{2})[/-](\d{1,2})[/-](\d{1,2})\b", text)
        if m:
            try:
                return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            except ValueError:
                return None

        m = re.search(r"\b(\d{1,2})[/-](\d{1,2})[/-](20\d{2})\b", text)
        if m:
            try:
                return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            except ValueError:
                return None

        # Jalali: 28 شهریور / «بیست و هشت شهریور» / «بیستو هشت شهریور».
        jalali_names = "|".join(map(re.escape, JALALI_MONTHS))
        m = re.search(
            rf"\b(?P<day>{NUMBER_PHRASE})\s+(?P<month>{jalali_names})(?:\s+(?P<year>1[34]\d{{2}}))?\b",
            text,
        )
        if m:
            day_value = parse_number_phrase(m.group("day"))
            if day_value is None or int(day_value) != day_value:
                return None
            day = int(day_value)
            month = JALALI_MONTHS[m.group("month")]
            current_j_year, _, _ = gregorian_to_jalali(today)
            year_raw = m.group("year")
            year = int(year_raw) if year_raw else current_j_year
            try:
                candidate = jalali_to_gregorian(year, month, day)
                if not year_raw and candidate < today:
                    candidate = jalali_to_gregorian(year + 1, month, day)
                return candidate
            except ValueError:
                return None

        # Gregorian month names: 19 سپتامبر / نوزده سپتامبر / September 19.
        # Voice transcription often emits Persian number words instead of digits.
        greg_names = "|".join(sorted(map(re.escape, GREGORIAN_MONTHS), key=len, reverse=True))
        m = re.search(
            rf"\b(?P<day>{NUMBER_PHRASE})\s+(?P<month>{greg_names})(?:\s+(?P<year>20\d{{2}}))?\b",
            text,
            re.I,
        )
        if not m:
            m = re.search(
                rf"\b(?P<month>{greg_names})\s+(?P<day>{NUMBER_PHRASE})(?:\s+(?P<year>20\d{{2}}))?\b",
                text,
                re.I,
            )
        if m:
            month_name = m.group("month")
            day_value = parse_number_phrase(m.group("day"))
            year_raw = m.group("year")
            if day_value is None or int(day_value) != day_value:
                return None
            month = GREGORIAN_MONTHS[month_name.lower()]
            day = int(day_value)
            year = int(year_raw) if year_raw else today.year
            try:
                candidate = date(year, month, day)
                if not year_raw and candidate < today:
                    candidate = date(year + 1, month, day)
                return candidate
            except ValueError:
                return None

        if "پس فردا" in text or "پسفردا" in text:
            return today + timedelta(days=2)
        if "فردا" in text:
            return today + timedelta(days=1)
        if "امروز" in text:
            return today

        # Persian weekday. Explicit dates above intentionally win if both are present.
        normalized_weekdays = sorted(WEEKDAYS.items(), key=lambda x: len(x[0]), reverse=True)
        for name, target in normalized_weekdays:
            if name in text:
                delta = (target - today.weekday()) % 7
                # "شنبه" normally means the next upcoming Saturday; if today is Saturday,
                # interpret it as next week unless the user explicitly said "امروز".
                if delta == 0:
                    delta = 7
                return today + timedelta(days=delta)
        return None

    def extract_time(self, text: str, allow_bare_clock: bool = False) -> tuple[str | None, str | None, int | None]:
        text = normalize_text(text)
        daypart = self._daypart(text)

        range_pattern = re.compile(
            rf"(?:از\s+)?(?:ساعت\s*)?(?P<start>{CLOCK_ATOM})\s*(?:تا|الی|-)\s*(?:ساعت\s*)?(?P<end>{CLOCK_ATOM})"
        )
        m = range_pattern.search(text)
        if m:
            start_hm = self._parse_clock_atom(m.group("start"), daypart)
            end_hm = self._parse_clock_atom(m.group("end"), daypart)
            if start_hm and end_hm:
                start_min = start_hm[0] * 60 + start_hm[1]
                end_min = end_hm[0] * 60 + end_hm[1]
                duration = end_min - start_min
                if duration <= 0:
                    duration += 24 * 60
                if daypart is None and start_hm[0] <= 11:
                    return None, f"{start_hm[0]:02d}:{start_hm[1]:02d}", duration
                return f"{start_hm[0]:02d}:{start_hm[1]:02d}", None, duration

        single_pattern = re.compile(rf"(?:ساعت)\s*(?P<start>{CLOCK_ATOM})")
        m = single_pattern.search(text)
        if not m and allow_bare_clock:
            # Used only when bot explicitly asked "what time?", so a bare "6 عصر" is safe.
            m = re.search(rf"^\s*(?P<start>{CLOCK_ATOM})", text)
        if m:
            hm = self._parse_clock_atom(m.group("start"), daypart)
            if hm:
                if daypart is None and hm[0] <= 11:
                    return None, f"{hm[0]:02d}:{hm[1]:02d}", None
                return f"{hm[0]:02d}:{hm[1]:02d}", None, None
        return None, None, None

    def _daypart(self, text: str) -> str | None:
        if re.search(r"\b(?:صبح|صبحا)\b", text):
            return "am"
        if re.search(r"\b(?:عصر|شب|غروب|بعدازظهر|بعد از ظهر)\b", text):
            return "pm"
        if "ظهر" in text:
            return "noon"
        return None

    def _parse_clock_atom(self, atom: str, daypart: str | None) -> tuple[int, int] | None:
        atom = normalize_text(atom)
        minute = 0
        if ":" in atom:
            h_raw, m_raw = atom.split(":", 1)
            try:
                hour, minute = int(h_raw), int(m_raw)
            except ValueError:
                return None
        elif re.fullmatch(r"\d{1,2}", atom):
            hour = int(atom)
        else:
            if " و نیم" in atom:
                base = atom.replace(" و نیم", "")
                parsed = parse_number_phrase(base)
                minute = 30
            elif " و ربع" in atom:
                base = atom.replace(" و ربع", "")
                parsed = parse_number_phrase(base)
                minute = 15
            else:
                parsed = parse_number_phrase(atom)
            if parsed is None:
                return None
            hour = int(parsed)

        if hour > 23 or minute > 59:
            return None
        if daypart == "pm" and 1 <= hour < 12:
            hour += 12
        elif daypart == "noon" and 1 <= hour < 12:
            hour += 12
        elif daypart == "am" and hour == 12:
            hour = 0
        return hour, minute

    def extract_duration(self, text: str) -> int | None:
        text = normalize_text(text)

        # Common spoken Persian: «به مدت یک ساعت و نیم / یک ساعت و ربع».
        m = re.search(
            rf"به\s+مدت\s+({NUMBER_PHRASE})\s*ساعت\s+و\s+(نیم|ربع)",
            text,
        )
        if m:
            hours = parse_number_phrase(m.group(1))
            if hours is not None:
                extra = 30 if m.group(2) == "نیم" else 15
                return max(1, int(hours * 60 + extra))

        # Only treat an explicit "به مدت" phrase as event duration so it doesn't
        # collide with the reminder phrase.
        m = re.search(
            rf"به\s+مدت\s+({NUMBER_PHRASE})\s*ساعت(?:\s+و\s+({NUMBER_PHRASE})\s*(?:دقیقه|دیقه|دقه))?",
            text,
        )
        if m:
            hours = parse_number_phrase(m.group(1))
            extra_minutes = parse_number_phrase(m.group(2)) if m.group(2) else 0
            if hours is not None and extra_minutes is not None:
                return max(1, int(hours * 60 + extra_minutes))

        m = re.search(rf"به\s+مدت\s+({NUMBER_PHRASE})\s*(?:دقیقه|دیقه|دقه)", text)
        if m:
            minutes = parse_number_phrase(m.group(1))
            if minutes is not None:
                return max(1, int(minutes))
        return None

    def extract_reminder(self, text: str) -> int | None:
        text = normalize_text(text)
        m = re.search(rf"({NUMBER_PHRASE})\s*((?:دقیقه|دیقه|دقه)|ساعت)\s*(?:قبل|پیش)", text)
        if not m:
            return None
        value = parse_number_phrase(m.group(1))
        if value is None:
            return None
        minutes = int(value * (60 if m.group(2) == "ساعت" else 1))
        return max(0, min(minutes, 40320))

    def extract_recurrence(self, text: str) -> str | None:
        text = normalize_text(text)
        if "بدون تکرار" in text or "تکرار نداشته" in text:
            return None
        if "هر روز" in text:
            return "daily"
        if "هر هفته" in text:
            return "weekly"
        if "هر ماه" in text:
            return "monthly"
        if any(re.search(rf"هر\s+{re.escape(day)}\b", text) for day in WEEKDAYS):
            return "weekly"
        return None
