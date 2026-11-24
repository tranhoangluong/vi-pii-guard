"""Text normalization helpers for Vietnamese input."""

from __future__ import annotations

import unicodedata
from functools import lru_cache


def normalize(text: str) -> str:
    """Return the NFC form of ``text``.

    Vietnamese text often arrives decomposed (NFD) from some keyboards and
    operating systems, which breaks regexes and tokenizers. All offsets
    produced by this library refer to the NFC form.
    """
    return unicodedata.normalize("NFC", text)


@lru_cache(maxsize=4096)
def _fold_char(char: str) -> str:
    if char in ("đ", "Đ"):
        return "d"
    decomposed = unicodedata.normalize("NFD", char)
    base = decomposed[0]
    if all(unicodedata.combining(c) for c in decomposed[1:]):
        return base.casefold()[:1] or base
    return char.casefold()[:1] or char


def fold(text: str) -> str:
    """Lowercase and strip Vietnamese diacritics while preserving length.

    ``fold("Số điện thoại")`` returns ``"so dien thoai"``. Because every
    character maps to exactly one character, offsets in the folded text are
    valid offsets in the original text. This lets context keywords match
    both accented and unaccented typing.
    """
    return "".join(_fold_char(c) for c in text)


def strip_diacritics(text: str) -> str:
    """Remove diacritics but keep the original casing (``Đ`` becomes ``D``)."""
    text = text.replace("đ", "d").replace("Đ", "D")
    decomposed = unicodedata.normalize("NFD", text)
    return unicodedata.normalize(
        "NFC", "".join(c for c in decomposed if not unicodedata.combining(c))
    )


_ASCII_DIGITS = frozenset("0123456789")


def digits_only(text: str) -> str:
    return "".join(c for c in text if c in _ASCII_DIGITS)
