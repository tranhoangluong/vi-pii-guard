"""Rule-based person-name baseline driven by Vietnamese trigger phrases.

Vietnamese names are written as 2-4 capitalized syllables ("Nguyễn Văn An").
Without a trigger, capitalized words are too ambiguous (places, brands), so
this recognizer only fires after phrases such as "tên là", "họ tên" or kinship
terms ("anh", "chị"). It is a baseline for the NER model, not a replacement.
"""

from __future__ import annotations

import re

from vi_pii_guard.domain import EntityType, Span
from vi_pii_guard.normalize import fold

_STRONG_TRIGGERS = (
    "tên là", "tên tôi là", "tên em là", "tên mình là", "tôi tên", "em tên", "mình tên",
    "họ tên", "họ và tên", "chủ tài khoản", "chủ tk", "khách hàng", "người nhận",
    "người gửi", "bệnh nhân", "ứng viên", "hành khách", "tài xế", "my name is",
)  # fmt: skip
# "tôi là" is ambiguous ("tôi là sinh viên"); the capitalized-name check filters most noise.
_SELF_TRIGGERS = ("tôi là", "em là", "mình là", "tớ là", "con là", "cháu là")
_KINSHIP_TRIGGERS = ("anh", "chị", "ông", "bà", "cô", "chú", "bác", "em", "bạn")


def _alternation(words: tuple[str, ...]) -> str:
    return "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True))


# Lookahead capture finds overlapping triggers ("tôi tên" and "tên là").
_STRONG_PATTERN = re.compile(
    r"(?<!\w)(?=(" + _alternation(tuple(fold(t) for t in _STRONG_TRIGGERS)) + r")(?!\w))"
)
_SELF_PATTERN = re.compile(
    r"(?<!\w)(?=(" + _alternation(tuple(fold(t) for t in _SELF_TRIGGERS)) + r")(?!\w))"
)
_KINSHIP_PATTERN = re.compile(
    r"(?<!\w)(?:" + _alternation(_KINSHIP_TRIGGERS) + r")(?!\w)",
    re.IGNORECASE,
)
# Skips ":" and the copula "là" between a trigger and the name.
# Capitalized job titles that follow "tôi là" ("Tôi là Giám đốc") are not names.
_TITLE_WORDS = frozenset(
    {"giám", "trưởng", "phó", "nhân", "kỹ", "kế", "quản", "chủ", "giáo", "sinh", "bác", "tổng"}
)
_SEPARATOR = re.compile(r"(?:[\s:]+|(?<=\s)l[àa](?=\s))*", re.IGNORECASE)
_TOKEN = re.compile(r"[^\W\d_]+")
_SENTENCE_START = re.compile(r"(?:^|[.!?\n]\s*)$")

STRONG_SCORE = 0.8
SELF_SCORE = 0.65
KINSHIP_SCORE = 0.6


class TriggerNameRecognizer:
    name = "names"

    def __init__(self, max_tokens: int = 4) -> None:
        self._max_tokens = max_tokens

    def recognize(self, text: str) -> list[Span]:
        spans: list[Span] = []
        folded = fold(text)
        for match in _STRONG_PATTERN.finditer(folded):
            span = self._name_after(text, match.end(1), STRONG_SCORE, min_tokens=1)
            if span is not None:
                spans.append(span)
        for match in _SELF_PATTERN.finditer(folded):
            span = self._name_after(text, match.end(1), SELF_SCORE, min_tokens=1)
            if span is not None:
                spans.append(span)
        for match in _KINSHIP_PATTERN.finditer(text):
            word = match.group(0)
            capitalized = word[0].isupper()
            if capitalized and not _SENTENCE_START.search(text[: match.start()]):
                # "Anh Quốc" mid-sentence is more likely a place than a kinship term.
                continue
            span = self._name_after(text, match.end(), KINSHIP_SCORE, min_tokens=1)
            if span is not None:
                spans.append(span)
        return spans

    def _name_after(
        self, text: str, position: int, score: float, *, min_tokens: int
    ) -> Span | None:
        separator = _SEPARATOR.match(text, position)
        cursor = separator.end() if separator else position
        start = cursor
        end = cursor
        tokens = 0
        while tokens < self._max_tokens:
            token = _TOKEN.match(text, cursor)
            if token is None or not token.group(0)[0].isupper():
                break
            if tokens == 0 and token.group(0).lower() in _TITLE_WORDS:
                return None
            end = token.end()
            tokens += 1
            if end < len(text) and text[end] == " ":
                cursor = end + 1
            else:
                break
        if tokens < min_tokens or end <= start:
            return None
        single = text[start:end]
        if tokens == 1 and single.isupper() and len(single) <= 4:
            return None  # acronyms such as "VIP", "CSKH"
        return Span(
            start=start,
            end=end,
            entity_type=EntityType.PERSON,
            text=text[start:end],
            score=score,
            source=self.name,
        )
