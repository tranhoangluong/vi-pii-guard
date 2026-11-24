"""Application facade: detect, redact and restore PII."""

from __future__ import annotations

import re
import secrets
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from typing import Literal

from vi_pii_guard.domain import EntityType, Recognizer, Span
from vi_pii_guard.normalize import digits_only, normalize
from vi_pii_guard.recognizers import default_recognizers
from vi_pii_guard.resolver import resolve_overlaps
from vi_pii_guard.validators import normalize_phone
from vi_pii_guard.vault import InMemoryVault, RedactionSession, Vault

Strategy = Literal["placeholder", "mask"]

_NUMERIC_TYPES = frozenset(
    {
        EntityType.NATIONAL_ID,
        EntityType.TAX_CODE,
        EntityType.BANK_ACCOUNT,
        EntityType.CARD_NUMBER,
    }
)
_PLACEHOLDER = re.compile(
    r"\[\s*(" + "|".join(e.value for e in EntityType) + r")_(\d+)\s*\]"
    r"|(?<![\w\[])(" + "|".join(e.value for e in EntityType) + r")_(\d+)(?![\w\]])"
)


@dataclass(frozen=True, slots=True)
class RedactedItem:
    span: Span
    replacement: str


@dataclass(frozen=True, slots=True)
class RedactionResult:
    text: str
    session_id: str | None
    items: tuple[RedactedItem, ...]


class Guard:
    """Detects Vietnamese PII and replaces it before text leaves your system.

    >>> guard = Guard.default()
    >>> result = guard.redact("Tôi tên là Nguyễn Văn An, SĐT 0912345678")
    >>> result.text
    'Tôi tên là [PERSON_1], SĐT [PHONE_1]'
    >>> guard.restore("Chào [PERSON_1]!", result.session_id)
    'Chào Nguyễn Văn An!'
    """

    def __init__(
        self,
        recognizers: Sequence[Recognizer],
        *,
        min_score: float = 0.5,
        entities: Collection[EntityType] | None = None,
        vault: Vault | None = None,
    ) -> None:
        if not 0.0 <= min_score <= 1.0:
            raise ValueError("min_score must be in [0, 1]")
        self._recognizers = tuple(recognizers)
        self._min_score = min_score
        self._entities = frozenset(entities) if entities is not None else frozenset(EntityType)
        self._vault: Vault = vault if vault is not None else InMemoryVault()

    @classmethod
    def default(
        cls,
        *,
        ner_model: str | None = None,
        min_score: float = 0.5,
        entities: Collection[EntityType] | None = None,
        vault: Vault | None = None,
    ) -> Guard:
        """Rule-based recognizers, plus a Hugging Face NER model when given."""
        recognizers = default_recognizers()
        if ner_model:
            from vi_pii_guard.recognizers.ner import TransformersNerRecognizer

            recognizers.append(TransformersNerRecognizer(ner_model))
        return cls(recognizers, min_score=min_score, entities=entities, vault=vault)

    @property
    def recognizer_names(self) -> tuple[str, ...]:
        return tuple(r.name for r in self._recognizers)

    def detect(self, text: str) -> list[Span]:
        """Return non-overlapping spans. Offsets refer to ``normalize(text)``."""
        normalized = normalize(text)
        candidates = [
            span
            for recognizer in self._recognizers
            for span in recognizer.recognize(normalized)
            if span.entity_type in self._entities and span.score >= self._min_score
        ]
        return resolve_overlaps(candidates)

    def redact(
        self,
        text: str,
        *,
        session_id: str | None = None,
        strategy: Strategy = "placeholder",
    ) -> RedactionResult:
        """Replace detected PII.

        ``placeholder`` (default) is reversible within a session: pass the
        returned ``session_id`` to :meth:`restore` or to the next ``redact``
        call of the same conversation. ``mask`` is irreversible (``[PHONE]``).
        An unknown or expired ``session_id`` starts a new session with a fresh
        random id, so a client can never attach to someone else's mapping.
        """
        normalized = normalize(text)
        spans = self.detect(normalized)
        session: RedactionSession | None = None
        if strategy == "placeholder":
            session = self._vault.load(session_id) if session_id else None
            if session is None:
                session = RedactionSession(secrets.token_hex(16))

        pieces: list[str] = []
        items: list[RedactedItem] = []
        cursor = 0
        for span in spans:
            if session is None:
                replacement = f"[{span.entity_type.value}]"
            else:
                key = _value_key(span.entity_type, span.text)
                replacement = session.placeholder_for(span.entity_type, key, span.text)
            pieces.append(normalized[cursor : span.start])
            pieces.append(replacement)
            items.append(RedactedItem(span, replacement))
            cursor = span.end
        pieces.append(normalized[cursor:])

        if session is not None:
            self._vault.save(session)
        return RedactionResult(
            text="".join(pieces),
            session_id=session.session_id if session else None,
            items=tuple(items),
        )

    def restore(self, text: str, session_id: str) -> str:
        """Put original values back into text that contains placeholders.

        Tolerates the light reformatting LLMs sometimes apply, such as
        ``[ PERSON_1 ]`` or a bare ``PERSON_1``. Unknown placeholders are left as is.
        """
        session = self._vault.load(session_id)
        if session is None:
            return text

        def replace(match: re.Match[str]) -> str:
            entity = match.group(1) or match.group(3)
            number = match.group(2) or match.group(4)
            return session.reverse.get(f"[{entity}_{number}]", match.group(0))

        return _PLACEHOLDER.sub(replace, text)

    def forget(self, session_id: str) -> None:
        """Delete a session mapping as soon as the conversation is over."""
        self._vault.delete(session_id)


def _value_key(entity_type: EntityType, value: str) -> str:
    """Key used to give equal values the same placeholder ("0912 345 678" == "0912345678")."""
    if entity_type is EntityType.PHONE:
        return normalize_phone(value)
    if entity_type in _NUMERIC_TYPES:
        return digits_only(value) or value
    if entity_type is EntityType.LICENSE_PLATE:
        return re.sub(r"[\s.\-]", "", value).upper()
    # Keep diacritics: "Lan" and "Lân" are different people.
    return " ".join(value.casefold().split())
