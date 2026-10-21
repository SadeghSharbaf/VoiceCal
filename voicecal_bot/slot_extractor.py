from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from difflib import SequenceMatcher

from .models import EventDraft
from .parser import EventParser
from .text_utils import normalize_text, parse_number_phrase


@dataclass(frozen=True)
class AnchorMatch:
    field: str
    start: int
    end: int
    raw: str
    score: float = 1.0


@dataclass
class CommandParseResult:
    draft: EventDraft
    anchors: dict[str, str] = field(default_factory=dict)
    slot_text: dict[str, str] = field(default_factory=dict)
    pending_fields: list[str] = field(default_factory=list)


# The voice protocol is intentionally small.  The user can speak naturally, but
# these marker words give us deterministic boundaries between free-form title and
# structured calendar values.
ANCHOR_ALIASES: dict[str, tuple[str, ...]] = {
    "title": (
        "موضوع",
        "عنوان",
        "با موضوع",
        "با عنوان",
        "موزوه",
        "موزوع",
        "موضوه",
    ),
    "date": (
        "تاریخ",
    ),
    "start_time": (
        "ساعت",
        "ساعت شروع",
    ),
    "duration": (
        "مدت",
        "به مدت",
    ),
    "reminder": (
        "یادآور",
        "یاداور",
        "یادآوری",
        "یاداوری",
        "آلارم",
        "الارم",
        "هشدار",
    ),
}

# Fuzzy matching is only used for the marker words, never for the values or title.
# This makes errors such as «ژاریخ» -> «تاریخ» recoverable without guessing user
# content.
FUZZY_TARGETS: dict[str, tuple[str, ...]] = {
    "title": ("موضوع", "عنوان"),
    "date": ("تاریخ",),
    "start_time": ("ساعت",),
    "duration": ("مدت",),
    "reminder": ("یادآور", "یادآوری", "آلارم", "هشدار"),
}

FIELD_ORDER = ["title", "date", "time_period", "start_time", "duration", "reminder"]


def _clean_token(token: str) -> str:
    return re.sub(r"[^\w\u0600-\u06FF]", "", token, flags=re.UNICODE)


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


class AnchorSlotExtractor:
    """Parse one voice/text command using explicit Persian anchor words.

    Recommended protocol:
        موضوع ... تاریخ ... ساعت ... مدت ... یادآور ...

    The order is flexible.  Existing EventParser routines still parse each value,
    but they receive a small field-specific fragment instead of one large sentence.
    """

    def __init__(self, parser: EventParser):
        self.parser = parser

    def detect_anchors(self, text: str) -> list[AnchorMatch]:
        text = normalize_text(text)
        candidates: list[AnchorMatch] = []

        # Exact aliases first, including multi-word forms.
        for field_name, aliases in ANCHOR_ALIASES.items():
            for alias in sorted(aliases, key=len, reverse=True):
                # Persian word boundaries are more reliable with negative \w than
                # plain \b around ZWNJ/Unicode punctuation.
                pattern = re.compile(
                    rf"(?<!\w){re.escape(alias)}(?!\w)", re.IGNORECASE
                )
                for match in pattern.finditer(text):
                    candidates.append(
                        AnchorMatch(field_name, match.start(), match.end(), match.group(0), 1.0)
                    )

        # Single-token fuzzy recovery for ASR-corrupted anchors.  Exact aliases
        # always win during overlap resolution.
        token_iter = list(re.finditer(r"\S+", text))
        for token_match in token_iter:
            token = _clean_token(token_match.group(0))
            if len(token) < 3:
                continue
            for field_name, targets in FUZZY_TARGETS.items():
                best = max((_similarity(token, target) for target in targets), default=0.0)
                # A higher threshold keeps arbitrary title words from becoming
                # anchors.  0.78 still catches e.g. ژاریخ/تاریخ and الارم/آلارم.
                if best >= 0.78:
                    candidates.append(
                        AnchorMatch(
                            field_name,
                            token_match.start(),
                            token_match.end(),
                            token_match.group(0),
                            best,
                        )
                    )

        # Resolve overlaps: prefer exact, then longer spans.  This prevents both
        # «به مدت» and «مدت» from being emitted at the same position.
        candidates.sort(key=lambda a: (a.start, -a.score, -(a.end - a.start)))
        selected: list[AnchorMatch] = []
        for candidate in candidates:
            overlap = next(
                (
                    existing
                    for existing in selected
                    if not (candidate.end <= existing.start or candidate.start >= existing.end)
                ),
                None,
            )
            if overlap is None:
                selected.append(candidate)
                continue
            better = (candidate.score, candidate.end - candidate.start) > (
                overlap.score,
                overlap.end - overlap.start,
            )
            if better:
                selected.remove(overlap)
                selected.append(candidate)

        selected.sort(key=lambda a: a.start)

        # «ساعت» is both a time anchor and a duration/reminder unit.  When it
        # follows a duration/reminder anchor with a numeric phrase in between, it
        # is a unit ("مدت یک ساعت"), not a new time slot.
        filtered: list[AnchorMatch] = []
        for candidate in selected:
            if (
                candidate.field == "start_time"
                and normalize_text(candidate.raw) == "ساعت"
                and filtered
                and filtered[-1].field in {"duration", "reminder"}
            ):
                between = text[filtered[-1].end : candidate.start].strip(" ،,.؛;:-")
                between = re.sub(r"^(?:هم|حدود|تقریبا|تقریباً)\s+", "", between)
                if parse_number_phrase(between) is not None:
                    continue
            filtered.append(candidate)

        return filtered

    def split_slots(self, text: str, anchors: list[AnchorMatch]) -> dict[str, str]:
        text = normalize_text(text)
        slots: dict[str, str] = {}
        for index, anchor in enumerate(anchors):
            value_start = anchor.end
            value_end = anchors[index + 1].start if index + 1 < len(anchors) else len(text)
            value = text[value_start:value_end].strip(" \t\n،,.؛;:-")
            # If a field is repeated, keep the last non-empty value.  In spoken
            # self-corrections the later value is usually intentional.
            if value or anchor.field not in slots:
                slots[anchor.field] = value
        return slots

    def parse(self, text: str, now: datetime) -> CommandParseResult:
        normalized = normalize_text(text)
        anchors = self.detect_anchors(normalized)

        # Existing free-form parser remains a useful fallback when users don't use
        # the protocol at all.  Protocol slots override it where available.
        draft = self.parser.parse(normalized, now)
        detected = {a.field: a.raw for a in anchors}
        slots = self.split_slots(normalized, anchors)
        issues: list[str] = []

        if "title" in detected:
            title = self._parse_title_fragment(slots.get("title", ""))
            draft.title = title
            if not title:
                issues.append("title")

        if "date" in detected:
            fragment = slots.get("date", "")
            parsed_date = self.parser.extract_date(fragment, now) if fragment else None
            draft.date_iso = parsed_date.isoformat() if parsed_date else None
            if not parsed_date:
                issues.append("date")

        if "start_time" in detected:
            fragment = slots.get("start_time", "")
            start, ambiguous, _ = self.parser.extract_time(fragment, allow_bare_clock=True)
            # Some fragments need the marker reintroduced for the parser, e.g.
            # a fragment that starts with filler before the clock.
            if not start and not ambiguous and fragment:
                start, ambiguous, _ = self.parser.extract_time(
                    f"ساعت {fragment}", allow_bare_clock=True
                )
            draft.start_time = start
            draft.ambiguous_time = ambiguous
            if ambiguous:
                issues.append("time_period")
            elif not start:
                issues.append("start_time")

        if "duration" in detected:
            fragment = slots.get("duration", "")
            parsed_duration = self._parse_duration_fragment(fragment)
            if parsed_duration is None:
                issues.append("duration")
            else:
                draft.duration_minutes = parsed_duration

        if "reminder" in detected:
            fragment = slots.get("reminder", "")
            parsed_reminder = self._parse_reminder_fragment(fragment)
            if parsed_reminder is None:
                issues.append("reminder")
            else:
                draft.reminder_minutes = parsed_reminder

        # Required fields are still required even if their anchor was not spoken.
        if not draft.title:
            issues.append("title")
        if not draft.date_iso:
            issues.append("date")
        if draft.ambiguous_time and not draft.start_time:
            issues.append("time_period")
        elif not draft.start_time:
            issues.append("start_time")

        # Stable deterministic order and no duplicates.
        issue_set = set(issues)
        pending = [field for field in FIELD_ORDER if field in issue_set]
        draft.pending_fields = pending.copy()
        draft.source_text = normalized
        return CommandParseResult(
            draft=draft,
            anchors=detected,
            slot_text=slots,
            pending_fields=pending,
        )

    @staticmethod
    def _parse_title_fragment(fragment: str) -> str | None:
        fragment = normalize_text(fragment).strip(" .،؛:-")
        # Remove small filler phrases immediately after the marker while preserving
        # the user's actual free-form subject text.
        fragment = re.sub(r"^(?:رو|را|این|یه|یک)\s+", "", fragment)
        fragment = re.sub(r"\s+(?:باشه|باشد|بذار|بزار|ست\s+کن)$", "", fragment)
        return fragment.strip(" .،؛:-") or None

    def _parse_duration_fragment(self, fragment: str) -> int | None:
        fragment = normalize_text(fragment)
        if not fragment:
            return None
        value = self.parser.extract_duration(f"به مدت {fragment}")
        if value is not None:
            return value
        temp = EventDraft(duration_minutes=self.parser.default_duration_minutes)
        if self.parser.patch_missing(temp, "duration", fragment, datetime.now()):
            return temp.duration_minutes
        return None

    def _parse_reminder_fragment(self, fragment: str) -> int | None:
        fragment = normalize_text(fragment)
        if not fragment:
            return None
        value = self.parser.extract_reminder(fragment)
        if value is not None:
            return value
        temp = EventDraft(reminder_minutes=self.parser.default_reminder_minutes)
        if self.parser.patch_missing(temp, "reminder", fragment, datetime.now()):
            return temp.reminder_minutes
        return None
