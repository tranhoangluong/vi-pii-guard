"""Rule-based address baseline.

Fires after an address trigger ("địa chỉ", "giao đến", "thường trú", ...) and
keeps the following clause if it contains an administrative keyword. Both the
pre-2025 three-level format (phường, quận, tỉnh) and the post-2025 two-level
format (phường/xã, tỉnh/thành phố) are accepted.
"""

from __future__ import annotations

import re

from vi_pii_guard.domain import EntityType, Span
from vi_pii_guard.normalize import fold
from vi_pii_guard.recognizers.context import KeywordSet

_TRIGGERS = KeywordSet(
    [
        "địa chỉ", "đ/c", "đc", "sống tại", "ở tại", "cư trú tại", "thường trú", "tạm trú",
        "giao đến", "giao tới", "giao hàng đến", "giao hàng tới", "gửi đến", "gửi về",
        "nhà ở", "address",
    ]
)  # fmt: skip
_ADMIN_KEYWORDS = KeywordSet(
    [
        "phường", "xã", "quận", "huyện", "tỉnh", "thành phố", "tp", "thị trấn", "thị xã",
        "đường", "ấp", "thôn", "khu phố", "tổ dân phố", "hẻm", "ngõ", "ngách",
    ]
)  # fmt: skip
# Words that may sit between a trigger and the address itself.
_MODIFIERS = KeywordSet(
    [
        "giao hàng", "nhận hàng", "liên hệ", "hiện tại", "hiện nay", "cũ", "mới", "là",
        "công ty", "nhà", "của tôi", "của em", "của mình", "tại",
    ]
)  # fmt: skip
# After a comma, these words start a new field rather than continuing the address.
_FIELD_STARTERS = (
    "sđt", "số điện thoại", "điện thoại", "email", "cccd", "cmnd", "mst", "stk",
    "số tài khoản", "liên hệ", "zalo", "hotline", "người nhận", "ngày sinh",
)  # fmt: skip
_FIELD_START = re.compile(
    r"\s*(?:" + "|".join(re.escape(fold(w)) for w in _FIELD_STARTERS) + r")(?!\w)"
)
_ABBREVIATIONS = frozenset({"tp", "p", "q", "tx", "tt", "h", "st"})
_SEPARATOR = re.compile(r"[\s:\-]*")
_LAST_TOKEN = re.compile(r"(\w+)$")

SCORE = 0.6
MAX_LENGTH = 160


class TriggerAddressRecognizer:
    name = "address"

    def recognize(self, text: str) -> list[Span]:
        folded = fold(text)
        spans: list[Span] = []
        for trigger in _TRIGGERS.finditer(folded):
            start = self._skip_prefix(text, folded, trigger.end())
            end = self._clause_end(text, folded, start)
            end = _trim_to_admin_segments(text, folded, start, end)
            while end > start and text[end - 1] in " ,;.-":
                end -= 1
            if end - start < 6 or not _ADMIN_KEYWORDS.search(folded, start, end):
                continue
            spans.append(
                Span(
                    start=start,
                    end=end,
                    entity_type=EntityType.ADDRESS,
                    text=text[start:end],
                    score=SCORE,
                    source=self.name,
                )
            )
        return spans

    @staticmethod
    def _skip_prefix(text: str, folded: str, position: int) -> int:
        """Skip separators, chained triggers and modifiers ("địa chỉ giao hàng: ...")."""
        while True:
            separator = _SEPARATOR.match(text, position)
            position = separator.end() if separator else position
            keyword = _TRIGGERS.match(folded, position) or _MODIFIERS.match(folded, position)
            if keyword is None:
                return position
            position = keyword.end()

    @staticmethod
    def _clause_end(text: str, folded: str, start: int) -> int:
        limit = min(len(text), start + MAX_LENGTH)
        for index in range(start, limit):
            char = text[index]
            if char in "\n;":
                return index
            if char == "." and _is_sentence_end(text, folded, index):
                return index
            if char == "," and _FIELD_START.match(folded, index + 1):
                return index
        return limit


_WORD = re.compile(r"\S+")


def _is_name_like(token: str) -> bool:
    core = token.strip(".,()")
    return bool(core) and (core[0].isupper() or core[0].isdigit())


def _trim_to_admin_segments(text: str, folded: str, start: int, end: int) -> int:
    """Cut trailing prose after the last administrative segment.

    "12 Lê Lợi, phường Bến Thành, TP. Hồ Chí Minh bị trễ 3 ngày" keeps everything up
    to "Minh": after the street, each comma segment must be an administrative
    keyword followed by capitalized words or numbers ("quận 1", "Hà Nội").
    Fully lowercase input (typed without capitals) is left untouched.
    """
    if not any(c.isupper() for c in text[start:end]):
        return end
    first_comma = text.find(",", start, end)
    if first_comma == -1:
        return end
    kept_end = first_comma
    position = first_comma + 1
    while position < end:
        comma = text.find(",", position, end)
        segment_end = end if comma == -1 else comma
        cursor = position
        while cursor < segment_end and text[cursor].isspace():
            cursor += 1
        keyword = _ADMIN_KEYWORDS.match(folded, cursor)
        if keyword is not None:
            cursor = keyword.end()
            while cursor < segment_end and text[cursor] in ". ":
                cursor += 1
        accepted = keyword is not None
        segment_stop = cursor
        for token in _WORD.finditer(text, cursor, segment_end):
            if not _is_name_like(token.group(0)):
                break
            accepted = True
            segment_stop = token.end()
        if not accepted:
            return kept_end
        kept_end = segment_stop
        if segment_stop < segment_end and text[segment_stop:segment_end].strip():
            return kept_end  # prose continues inside this segment
        position = segment_end + 1
    return kept_end


def _is_sentence_end(text: str, folded: str, index: int) -> bool:
    next_char = text[index + 1] if index + 1 < len(text) else " "
    if not next_char.isspace():
        return False  # "TP.HCM", "12.5"
    last = _LAST_TOKEN.search(folded[:index])
    return last is None or last.group(1) not in _ABBREVIATIONS
