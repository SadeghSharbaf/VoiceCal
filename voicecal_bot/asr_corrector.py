from __future__ import annotations

import re
from difflib import SequenceMatcher

from .text_utils import normalize_text


# This layer is intentionally conservative.  It only fixes words that are highly
# likely to be calendar vocabulary, and it uses context for riskier corrections.
# The event title itself is left mostly untouched so a legitimate title is not
# silently rewritten.

_EXACT_REPLACEMENTS = {
    # Gregorian month variants frequently produced by Persian ASR.
    "سبتمبر": "سپتامبر",
    "سبتامبر": "سپتامبر",
    "سبتومبر": "سپتامبر",
    "سپتمبر": "سپتامبر",
    "اکتوبر": "اکتبر",
    # Common calendar words.
    "ایوانت": "ایونت",
    "اونت": "ایونت",
    "موزوه": "موضوع",
    "موزوع": "موضوع",
    "موضوه": "موضوع",
    "یاداور": "یادآور",
    "یاداوری": "یادآوری",
    "دیقه": "دقیقه",
    "دقه": "دقیقه",
}

_DAYPART_ALIASES = {
    "آسر": "عصر",
    "اسر": "عصر",
    "اصر": "عصر",
    "عسر": "عصر",
    "آصر": "عصر",
    "عزر": "عصر",
    "ازره": "عصر",
    "ازر": "عصر",
    "صب": "صبح",
    "سوب": "صبح",
}


def _similar(a: str, b: str, threshold: float = 0.72) -> bool:
    return SequenceMatcher(a=a, b=b).ratio() >= threshold


def correct_calendar_asr(text: str) -> str:
    """Repair high-confidence Persian ASR errors for calendar commands.

    The function is deterministic and local.  It does not call an LLM or any
    external API.  It is designed to improve command words while avoiding broad
    rewrites of user titles.
    """

    text = normalize_text(text)

    # Fix a few joined/inflected forms before token-level replacements.
    text = re.sub(r"(?<!\w)یاداور(?:ایم|م)(?!\w)", "یادآور هم", text)
    text = re.sub(r"(?<!\w)یاداوری(?:م)?(?!\w)", "یادآوری", text)

    # Exact token fixes first.
    for src, dst in _EXACT_REPLACEMENTS.items():
        text = re.sub(rf"(?<!\w){re.escape(src)}(?!\w)", dst, text, flags=re.IGNORECASE)

    # Whisper sometimes joins ساعت and شیش/شش: ساعتشیشه, ساعتشیش, ...
    text = re.sub(r"(?<!\w)ساعت\s*شیشه(?!\w)", "ساعت شیش", text)
    text = re.sub(r"(?<!\w)ساعت\s*شیش(?!\w)", "ساعت شیش", text)

    # Observed short-voice corruption: "ساعت شیشه اصدی ایوانت" for
    # "ساعت شیش عصر یه ایونت".  Keep this contextual so اصدی in an
    # arbitrary event title is not rewritten.
    text = re.sub(r"(?<=ساعت شیش )اصدی(?=\s+ایونت\b)", "عصر یه", text)
    text = re.sub(r"(?<=ساعت شیش )اصدی(?=\s)", "عصر", text)

    # Another observed phrase before a duration: "بموضده تی یک ساعت".
    text = re.sub(r"(?<!\w)بموضده\s+تی(?=\s+(?:یک|یه|\d+)\s+ساعت)", "به مدت", text)

    # Colloquial split of nineteen.
    text = re.sub(r"(?<!\w)نوز\s+ده(?!\w)", "نوزده", text)

    # Very common reminder corruption observed in short Telegram voice notes.
    text = re.sub(
        r"(?<!\w)(?:پنین|پنجین|پنجی)\s+(?:دیگه|دیقه|دقه)(?!\w)",
        "پنج دقیقه",
        text,
    )
    text = re.sub(r"(?<!\w)یادآور(?:ایم|م)?(?!\w)", "یادآور هم", text)

    # Fix daypart tokens.  Exact aliases are safe anywhere; fuzzy correction is
    # only allowed when the utterance looks like a time answer/command.
    tokens = text.split()
    looks_time_related = bool(
        re.search(r"(?:^|\s)(?:ساعت|\d{1,2}(?::\d{1,2})?|شش|شیش|هفت|هشت|نه|ده)(?:\s|$)", text)
    )
    for i, token in enumerate(tokens):
        clean = token.strip(".,،؛:!?؟")
        if clean in _DAYPART_ALIASES:
            tokens[i] = token.replace(clean, _DAYPART_ALIASES[clean])
            continue
        if looks_time_related and len(clean) >= 3 and _similar(clean, "عصر", 0.72):
            tokens[i] = token.replace(clean, "عصر")
    text = " ".join(tokens)

    # Context-only correction: "شیشه عصر" is almost certainly "شیش عصر" in a
    # clock command, while the word شیشه may be legitimate in an event title.
    text = re.sub(r"(?<!\w)شیشه\s+(?=عصر|صبح|شب|ظهر)", "شیش ", text)

    # Normalize common malformed marker only when it is followed by title text.
    text = re.sub(r"(?<!\w)(?:موزوه|موزوع|موضوه)(?=\s+)", "موضوع", text)

    # Remove accidental duplicate filler created by correction.
    text = re.sub(r"\bهم\s+هم\b", "هم", text)
    return normalize_text(text)
