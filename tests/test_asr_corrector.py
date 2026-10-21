from voicecal_bot.asr_corrector import correct_calendar_asr


def test_observed_month_error():
    assert correct_calendar_asr("نوز ده سبتومبر") == "نوزده سپتامبر"


def test_observed_daypart_error():
    assert correct_calendar_asr("شیشه آسر") == "شیش عصر"


def test_joined_clock_word():
    fixed = correct_calendar_asr("برای نوزده سپتامبر ساعتشیشه آسر")
    assert "ساعت شیش عصر" in fixed


def test_reminder_noise():
    fixed = correct_calendar_asr("یاداورایم پنین دیگه قبلش بزا")
    assert "یادآور هم" in fixed
    assert "پنج دقیقه" in fixed


def test_observed_followup_variant():
    assert "عصر" in correct_calendar_asr("منظور ششه ازره")


def test_full_observed_command_becomes_parseable():
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from voicecal_bot.parser import EventParser

    raw = (
        "برای نوزده سبتمبر ساعتشیشه اصدی ایوانت بموضده تی یک ساعت ست کن "
        "با موزوه تست ابلیکشه یاداورایم پنین دیگه قبلش بزا"
    )
    fixed = correct_calendar_asr(raw)
    draft = EventParser("Asia/Tehran", 60, 10).parse(
        fixed, datetime(2026, 9, 18, 12, 0, tzinfo=ZoneInfo("Asia/Tehran"))
    )
    assert draft.date_iso == "2026-09-19"
    assert draft.start_time == "18:00"
    assert draft.duration_minutes == 60
    assert draft.reminder_minutes == 5
    assert draft.title == "تست ابلیکشه"
