from __future__ import annotations

from datetime import date

from .jalali import gregorian_to_jalali
from .models import EventDraft


PERSIAN_MONTHS = [
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
]
PERSIAN_WEEKDAYS = {
    0: "دوشنبه",
    1: "سه‌شنبه",
    2: "چهارشنبه",
    3: "پنجشنبه",
    4: "جمعه",
    5: "شنبه",
    6: "یکشنبه",
}
RECURRENCE_LABEL = {
    None: "بدون تکرار",
    "daily": "هر روز",
    "weekly": "هر هفته",
    "monthly": "هر ماه",
}


def format_preview(draft: EventDraft) -> str:
    d = date.fromisoformat(draft.date_iso)  # draft is complete here
    jy, jm, jd = gregorian_to_jalali(d)
    start = draft.start_datetime()
    end = draft.end_datetime()

    jalali_text = f"{jd} {PERSIAN_MONTHS[jm - 1]} {jy}"
    gregorian_text = d.strftime("%Y-%m-%d")

    return (
        "📅 پیش‌نمایش رویداد\n\n"
        f"📝 {draft.title}\n"
        f"📆 {PERSIAN_WEEKDAYS[d.weekday()]}، {jalali_text}  ({gregorian_text})\n"
        f"🕒 {start.strftime('%H:%M')} → {end.strftime('%H:%M')}\n"
        f"⏱ مدت: {draft.duration_minutes} دقیقه\n"
        f"🔔 یادآوری: {draft.reminder_minutes} دقیقه قبل\n"
        f"🔁 {RECURRENCE_LABEL.get(draft.recurrence, draft.recurrence)}\n\n"
        "اگر درست است تأیید کن."
    )
