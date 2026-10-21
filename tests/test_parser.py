from datetime import datetime
from zoneinfo import ZoneInfo

from voicecal_bot.parser import EventParser


TZ = ZoneInfo("Asia/Tehran")
NOW = datetime(2026, 9, 18, 12, 0, tzinfo=TZ)


def parser():
    return EventParser("Asia/Tehran", 60, 10)


def test_jalali_full_command():
    d = parser().parse(
        "برای تاریخ 28 شهریور ساعت 18 یه ایونت به مدت یک ساعت ست کن با موضوع رسیدگی به پروژه های فلان یادآور هم بزار پنج دقیقه قبلش",
        NOW,
    )
    assert d.date_iso == "2026-09-19"
    assert d.start_time == "18:00"
    assert d.duration_minutes == 60
    assert d.reminder_minutes == 5
    assert d.title == "رسیدگی به پروژه های فلان"


def test_gregorian_month_and_pm():
    d = parser().parse(
        "19 سپتامبر ساعت 9 شب به مدت یک ساعت با موضوع بررسی پروژه یادآور 10 دقیقه قبل",
        NOW,
    )
    assert d.date_iso == "2026-09-19"
    assert d.start_time == "21:00"
    assert d.title == "بررسی پروژه"


def test_ambiguous_time_asks_for_period():
    d = parser().parse("فردا ساعت 7 با موضوع مطالعه شبکه", NOW)
    assert d.date_iso == "2026-09-19"
    assert d.start_time is None
    assert d.ambiguous_time == "07:00"
    assert d.next_missing_field() == "time_period"


def test_weekday_range():
    d = parser().parse("شنبه از ساعت 18 تا 19 با موضوع کار روی پروژه", NOW)
    assert d.date_iso == "2026-09-19"
    assert d.start_time == "18:00"
    assert d.duration_minutes == 60


def test_weekly_recurrence_from_weekday():
    d = parser().parse("هر شنبه ساعت 18 با موضوع ورزش", NOW)
    assert d.date_iso == "2026-09-19"
    assert d.recurrence == "weekly"


def test_title_stops_before_duration():
    d = parser().parse(
        "فردا ساعت شش و نیم شب با موضوع مطالعه شبکه به مدت 90 دقیقه یادآور 15 دقیقه قبل",
        NOW,
    )
    assert d.title == "مطالعه شبکه"
    assert d.duration_minutes == 90


def test_colloquial_dighe_reminder():
    d = parser().parse(
        "19 سپتامبر ساعت 18 با موضوع پروژه یاداور پنج دیقه قبل",
        NOW,
    )
    assert d.reminder_minutes == 5


def test_gregorian_month_with_persian_number_word():
    d = parser().parse(
        "نوزده سپتامبر ساعت شش عصر با موضوع تست برنامه یادآور پنج دقیقه قبل",
        NOW,
    )
    assert d.date_iso == "2026-09-19"
    assert d.start_time == "18:00"
    assert d.title == "تست برنامه"
    assert d.reminder_minutes == 5


def test_common_asr_september_variants():
    for text in ["نوز ده سبتومبر", "نوزده سبتمبر", "نوزده سبتامبر"]:
        d = parser().parse(text + " ساعت شش عصر با موضوع تست", NOW)
        assert d.date_iso == "2026-09-19"


def test_jalali_date_with_spoken_compound_number():
    for spoken in ["بیست و هشت شهریور", "بیستو هشت شهریور", "بیستوهشت شهریور"]:
        d = parser().parse(f"{spoken} ساعت شش عصر با موضوع تست", NOW)
        assert d.date_iso == "2026-09-19"
        assert d.start_time == "18:00"


def test_spoken_compound_numbers_in_duration_and_reminder():
    d = parser().parse(
        "بیستو هشت شهریور ساعت شش عصر با موضوع تست به مدت یک ساعت یادآور پونزده دقیقه قبل",
        NOW,
    )
    assert d.date_iso == "2026-09-19"
    assert d.duration_minutes == 60
    assert d.reminder_minutes == 15


def test_24h_clock_with_number_words():
    d = parser().parse("فردا ساعت بیست و یک با موضوع مطالعه", NOW)
    assert d.start_time == "21:00"
    assert d.ambiguous_time is None
