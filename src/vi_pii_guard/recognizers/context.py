"""Keyword context matching on folded (lowercase, diacritic-free) text."""

from __future__ import annotations

import re
from collections.abc import Iterable

from vi_pii_guard.normalize import fold


class KeywordSet:
    """Matches whole-word keywords regardless of case and diacritics.

    ``KeywordSet(["số điện thoại"])`` matches "Số điện thoại", "so dien thoai"
    and "SO DIEN THOAI".
    """

    def __init__(self, keywords: Iterable[str]) -> None:
        folded = sorted({fold(k) for k in keywords if k.strip()}, key=len, reverse=True)
        self._pattern: re.Pattern[str] | None = (
            re.compile(r"(?<!\w)(?:" + "|".join(re.escape(k) for k in folded) + r")(?!\w)")
            if folded
            else None
        )

    def __bool__(self) -> bool:
        return self._pattern is not None

    def search(self, folded_text: str, start: int = 0, end: int | None = None) -> bool:
        if self._pattern is None:
            return False
        return (
            self._pattern.search(folded_text, start, len(folded_text) if end is None else end)
            is not None
        )

    def match(self, folded_text: str, position: int) -> re.Match[str] | None:
        """Match a keyword starting exactly at ``position``."""
        if self._pattern is None:
            return None
        return self._pattern.match(folded_text, position)

    def finditer(self, folded_text: str) -> Iterable[re.Match[str]]:
        if self._pattern is None:
            return iter(())
        return self._pattern.finditer(folded_text)
