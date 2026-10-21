from __future__ import annotations

import re


# Canonical Persian number words used by the parser.  A few common colloquial
# forms are included because Whisper often transcribes spoken Persian rather
# than formal written Persian.
PERSIAN_NUMBER_WORDS = {
    "صفر": 0,
    "یک": 1,
    "یه": 1,
    "دو": 2,
    "سه": 3,
    "چهار": 4,
    "پنج": 5,
    "شش": 6,
    "شیش": 6,
    "هفت": 7,
    "هشت": 8,
    "نه": 9,
    "ده": 10,
    "یازده": 11,
    "دوازده": 12,
    "سیزده": 13,
    "چهارده": 14,
    "پانزده": 15,
    "پونزده": 15,
    "شانزده": 16,
    "شونزده": 16,
    "هفده": 17,
    "هیفده": 17,
    "هجده": 18,
    "هیجده": 18,
    "نوزده": 19,
    "بیست": 20,
    "سی": 30,
    "چهل": 40,
    "پنجاه": 50,
    "شصت": 60,
    "هفتاد": 70,
    "هشتاد": 80,
    "نود": 90,
    "صد": 100,
    "دویست": 200,
    "سیصد": 300,
    "چهارصد": 400,
    "پانصد": 500,
    "ششصد": 600,
    "هفتصد": 700,
    "هشتصد": 800,
    "نهصد": 900,
}

# Reusable regex fragment.  It deliberately allows multiple number tokens so
# phrases such as «بیست و هشت», «بیستو هشت» (after normalization), or
# «یکصد و بیست» can be captured in calendar-specific contexts.
_NUMBER_WORDS = sorted(PERSIAN_NUMBER_WORDS, key=len, reverse=True)
NUMBER_WORD_PATTERN = "(?:" + "|".join(map(re.escape, _NUMBER_WORDS)) + ")"
NUMBER_PHRASE_PATTERN = rf"(?:\d+(?:\.\d+)?|(?:{NUMBER_WORD_PATTERN})(?:\s+و\s+(?:{NUMBER_WORD_PATTERN}|نیم|ربع))*)"

_DIGIT_TRANSLATION = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789",
)
_CHAR_TRANSLATION = str.maketrans({"ك": "ک", "ي": "ی", "ى": "ی", "ۀ": "ه", "ة": "ه"})


def _normalize_colloquial_number_connectors(text: str) -> str:
    """Normalize spoken Persian forms like «بیستو هشت» -> «بیست و هشت».

    The trailing spoken /o/ is only rewritten when the next token is itself a
    number word, so ordinary words/titles are not broadly modified.
    """

    next_number = NUMBER_WORD_PATTERN
    connector_roots = {
        "بیستو": "بیست و",
        "سیو": "سی و",
        "چهلو": "چهل و",
        "پنجاهو": "پنجاه و",
        "شصتو": "شصت و",
        "هفتادو": "هفتاد و",
        "هشتادو": "هشتاد و",
        "نودو": "نود و",
        "صدو": "صد و",
    }
    for src, dst in connector_roots.items():
        text = re.sub(rf"(?<!\w){re.escape(src)}\s+(?={next_number}(?!\w))", dst + " ", text)

    # Very common joined date forms from ASR, e.g. «بیستوهشت».
    tens = {
        "بیست": 20,
        "سی": 30,
        "چهل": 40,
        "پنجاه": 50,
        "شصت": 60,
        "هفتاد": 70,
        "هشتاد": 80,
        "نود": 90,
    }
    units = {
        "یک": 1, "یه": 1, "دو": 2, "سه": 3, "چهار": 4,
        "پنج": 5, "شش": 6, "شیش": 6, "هفت": 7, "هشت": 8, "نه": 9,
    }
    for t in tens:
        for u in units:
            text = re.sub(
                rf"(?<!\w){re.escape(t)}و{re.escape(u)}(?!\w)",
                f"{t} و {u}",
                text,
            )
    return text


def normalize_text(text: str) -> str:
    text = text.translate(_DIGIT_TRANSLATION).translate(_CHAR_TRANSLATION)
    text = text.replace("‌", " ")  # ZWNJ
    text = re.sub(r"\s+", " ", text).strip()

    # Conservative fixes for common Persian ASR spellings in our tiny calendar
    # vocabulary.  These are intentionally limited to unambiguous forms.
    replacements = {
        "سپتمبر": "سپتامبر",
        "سبتمبر": "سپتامبر",
        "سبتامبر": "سپتامبر",
        "سبتومبر": "سپتامبر",
        "اکتوبر": "اکتبر",
    }
    for src, dst in replacements.items():
        text = re.sub(rf"(?<!\w){re.escape(src)}(?!\w)", dst, text, flags=re.IGNORECASE)

    # Whisper can occasionally split نوزده into two tokens in colloquial speech.
    text = re.sub(r"(?<!\w)نوز\s+ده(?!\w)", "نوزده", text)
    text = _normalize_colloquial_number_connectors(text)
    return re.sub(r"\s+", " ", text).strip()


def parse_number_phrase(value: str) -> float | None:
    """Parse Persian/ASCII numeric phrases used in calendar commands.

    Examples: 28, «بیست و هشت», «بیستو هشت», «پونزده», «یک و نیم».
    The implementation is intentionally small but handles the ranges needed for
    dates, times, durations, reminders, and spoken Jalali years.
    """

    value = normalize_text(value).strip()
    if not value:
        return None

    try:
        return float(value)
    except ValueError:
        pass

    if value == "نیم":
        return 0.5
    if value == "ربع":
        return 0.25

    tokens = [t for t in re.split(r"\s+", value) if t and t != "و"]
    if not tokens:
        return None

    total = 0.0
    current = 0.0
    for token in tokens:
        if token == "نیم":
            current += 0.5
            continue
        if token == "ربع":
            current += 0.25
            continue
        if token == "هزار":
            # Enough for spoken years such as «هزار و چهارصد و پنج».
            current = (current or 1) * 1000
            total += current
            current = 0.0
            continue
        number = PERSIAN_NUMBER_WORDS.get(token)
        if number is None:
            return None
        current += number

    return total + current
