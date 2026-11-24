"""Conversions between character spans and token-level BIO tags.

Used by the NER training script; kept dependency-free so it can be tested
without ``transformers``. ``offsets`` are ``(start, end)`` character offsets
per token as returned by a fast tokenizer; ``(0, 0)`` marks special tokens.
"""

from __future__ import annotations

from collections.abc import Sequence

from vi_pii_guard.domain import EntityType

Triple = tuple[int, int, str]


def bio_labels(entities: Sequence[EntityType] = tuple(EntityType)) -> list[str]:
    return ["O"] + [f"{prefix}-{e.value}" for e in entities for prefix in ("B", "I")]


def spans_to_bio(offsets: Sequence[tuple[int, int]], spans: Sequence[Triple]) -> list[str | None]:
    """Tag each token. Special tokens get ``None`` (ignored by the loss)."""
    tags: list[str | None] = []
    previous_span: int | None = None
    for start, end in offsets:
        if start == end:
            tags.append(None)
            previous_span = None
            continue
        index = next(
            (i for i, (s, e, _) in enumerate(spans) if s <= start < e),
            None,
        )
        if index is None:
            tags.append("O")
        else:
            prefix = "I" if index == previous_span else "B"
            tags.append(f"{prefix}-{spans[index][2]}")
        previous_span = index
    return tags


def bio_to_spans(offsets: Sequence[tuple[int, int]], tags: Sequence[str | None]) -> list[Triple]:
    """Decode BIO tags back to character spans; a stray ``I-`` starts a new span."""
    spans: list[Triple] = []
    current: list[int | str] | None = None  # [start, end, label]
    for (start, end), tag in zip(offsets, tags, strict=True):
        if tag is None or start == end:
            continue
        if tag == "O":
            if current is not None:
                spans.append((int(current[0]), int(current[1]), str(current[2])))
                current = None
            continue
        prefix, _, label = tag.partition("-")
        if current is not None and prefix == "I" and current[2] == label:
            current[1] = end
            continue
        if current is not None:
            spans.append((int(current[0]), int(current[1]), str(current[2])))
        current = [start, end, label]
    if current is not None:
        spans.append((int(current[0]), int(current[1]), str(current[2])))
    return spans
