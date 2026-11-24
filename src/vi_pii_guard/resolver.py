"""Overlap resolution between candidate spans from several recognizers."""

from __future__ import annotations

from collections.abc import Iterable

from vi_pii_guard.domain import Span


def resolve_overlaps(spans: Iterable[Span]) -> list[Span]:
    """Keep a non-overlapping subset, preferring higher score, then longer spans.

    Example: "0312345675" may match both PHONE and TAX_CODE. Context scoring
    decides which one has the higher score; the other is dropped here.
    """
    ranked = sorted(spans, key=lambda s: (-s.score, -s.length, s.start, s.entity_type.value))
    chosen: list[Span] = []
    for candidate in ranked:
        if not any(candidate.overlaps(kept) for kept in chosen):
            chosen.append(candidate)
    return sorted(chosen, key=lambda s: s.start)
