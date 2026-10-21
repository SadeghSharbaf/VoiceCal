from datetime import datetime
from zoneinfo import ZoneInfo

from voicecal_bot.asr_corrector import correct_calendar_asr
from voicecal_bot.parser import EventParser
from voicecal_bot.slot_extractor import AnchorSlotExtractor


TZ = ZoneInfo("Asia/Tehran")
NOW = datetime(2026, 9, 18, 22, 0, tzinfo=TZ)


def extractor():
    parser = EventParser("Asia/Tehran", 60, 10)
    return AnchorSlotExtractor(parser)


def parse(text: str):
    return extractor().parse(correct_calendar_asr(text), NOW)


def test_protocol_full_command_is_split_by_anchors():
    result = parse(
        "موضوع رسیدگی به پروژه های فلان تاریخ بیستو هشت شهریور "
        "ساعت شش عصر مدت یک ساعت یادآور ده دقیقه قبل"
    )
    d = result.draft
    assert d.title == "رسیدگی به پروژه های فلان"
    assert d.date_iso == "2026-09-19"
    assert d.start_time == "18:00"
    assert d.duration_minutes == 60
    assert d.reminder_minutes == 10
    assert result.pending_fields == []


def test_hour_unit_inside_duration_is_not_a_time_anchor():
    result = parse(
        "موضوع تست تاریخ فردا ساعت 18 مدت یک ساعت و نیم یادآور یک ساعت قبل"
    )
    assert result.slot_text["start_time"] == "18"
    assert result.slot_text["duration"] == "یک ساعت و نیم"
    assert result.slot_text["reminder"].endswith("یک ساعت قبل")
    assert result.draft.duration_minutes == 90
    assert result.draft.reminder_minutes == 60
    assert result.pending_fields == []


def test_fuzzy_corrupted_date_anchor_is_recovered():
    result = parse(
        "موضوع تست ژاریخ بیست و هشت شهریور ساعت شیش عصر مدت یک ساعت الارم ده دقیقه قبل"
    )
    assert result.draft.date_iso == "2026-09-19"
    assert result.draft.start_time == "18:00"
    assert result.pending_fields == []


def test_only_broken_slot_is_queued():
    result = parse(
        "موضوع تست تاریخ فردا ساعت ایکی برد از دوور مدت یک ساعت یادآور ده دقیقه قبل"
    )
    assert result.draft.title == "تست"
    assert result.draft.date_iso == "2026-09-19"
    assert result.draft.duration_minutes == 60
    assert result.draft.reminder_minutes == 10
    assert result.pending_fields == ["start_time"]
    assert result.draft.next_missing_field() == "start_time"


def test_ambiguous_clock_only_asks_am_pm():
    result = parse(
        "موضوع مطالعه تاریخ فردا ساعت شش مدت یک ساعت یادآور پنج دقیقه قبل"
    )
    assert result.draft.ambiguous_time == "06:00"
    assert result.pending_fields == ["time_period"]


def test_protocol_order_can_change():
    result = parse(
        "یادآور پنج دقیقه قبل موضوع ورزش مدت نود دقیقه تاریخ فردا ساعت نوزده"
    )
    d = result.draft
    assert d.title == "ورزش"
    assert d.date_iso == "2026-09-19"
    assert d.start_time == "19:00"
    assert d.duration_minutes == 90
    assert d.reminder_minutes == 5
    assert result.pending_fields == []


def test_unspoken_optional_slots_keep_defaults():
    result = parse("موضوع تست تاریخ فردا ساعت 18")
    assert result.draft.duration_minutes == 60
    assert result.draft.reminder_minutes == 10
    assert result.pending_fields == []


def test_spoken_but_unparsed_optional_slot_is_asked():
    result = parse(
        "موضوع تست تاریخ فردا ساعت 18 مدت یه چیزی نامفهوم یادآور پنج دقیقه قبل"
    )
    assert result.pending_fields == ["duration"]
