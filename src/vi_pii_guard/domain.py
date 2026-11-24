"""Core domain types: entity taxonomy, detected spans and the recognizer port."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, runtime_checkable


class EntityType(StrEnum):
    """PII categories supported by the guard. See docs/entities.md for formats."""

    PERSON = "PERSON"
    ADDRESS = "ADDRESS"
    PHONE = "PHONE"
    EMAIL = "EMAIL"
    NATIONAL_ID = "NATIONAL_ID"
    PASSPORT = "PASSPORT"
    TAX_CODE = "TAX_CODE"
    BANK_ACCOUNT = "BANK_ACCOUNT"
    CARD_NUMBER = "CARD_NUMBER"
    LICENSE_PLATE = "LICENSE_PLATE"
    DATE_OF_BIRTH = "DATE_OF_BIRTH"


@dataclass(frozen=True, slots=True)
class Span:
    """A detected PII entity. Offsets refer to the NFC-normalized input text."""

    start: int
    end: int
    entity_type: EntityType
    text: str
    score: float
    source: str

    def __post_init__(self) -> None:
        if not 0 <= self.start < self.end:
            raise ValueError(f"invalid span offsets: [{self.start}, {self.end})")
        if not 0.0 <= self.score <= 1.0:
            raise ValueError(f"score must be in [0, 1], got {self.score}")

    @property
    def length(self) -> int:
        return self.end - self.start

    def overlaps(self, other: Span) -> bool:
        return self.start < other.end and other.start < self.end


@runtime_checkable
class Recognizer(Protocol):
    """Port implemented by every detection adapter (rules, NER models, ...)."""

    name: str

    def recognize(self, text: str) -> list[Span]:
        """Return candidate spans for an NFC-normalized text."""
        ...
