from datetime import date

from voicecal_bot.jalali import gregorian_to_jalali, jalali_to_gregorian


def test_known_1405_shahrivar_date():
    assert jalali_to_gregorian(1405, 6, 28) == date(2026, 9, 19)
    assert gregorian_to_jalali(date(2026, 9, 19)) == (1405, 6, 28)
