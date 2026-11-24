"""Regex recognizer with validators and keyword context scoring."""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from vi_pii_guard.domain import EntityType, Span
from vi_pii_guard.normalize import fold
from vi_pii_guard.recognizers.context import KeywordSet


@dataclass(frozen=True)
class PatternRule:
    """One regex-based detection rule.

    Scoring, in order:
      1. start at ``base_score``;
      2. if a validator exists: pass -> raise to ``validated_score``;
         fail -> drop the match when ``reject_invalid`` is set;
      3. positive context before/after the match adds ``context_boost``;
         ``require_context`` drops matches without it;
      4. negative context before the match subtracts ``negative_penalty``
         (e.g. a 10-digit number after "MST" is less likely a phone number).
    """

    entity_type: EntityType
    pattern: re.Pattern[str]
    base_score: float
    validator: Callable[[str], bool] | None = None
    validated_score: float | None = None
    reject_invalid: bool = False
    context: KeywordSet = field(default_factory=lambda: KeywordSet(()))
    context_boost: float = 0.0
    require_context: bool = False
    negative_context: KeywordSet = field(default_factory=lambda: KeywordSet(()))
    negative_penalty: float = 0.0


class PatternRecognizer:
    """Applies a list of :class:`PatternRule` to a text."""

    def __init__(
        self,
        rules: Sequence[PatternRule],
        *,
        name: str = "regex",
        window_before: int = 40,
        window_after: int = 15,
    ) -> None:
        self.name = name
        self._rules = tuple(rules)
        self._before = window_before
        self._after = window_after

    def recognize(self, text: str) -> list[Span]:
        folded = fold(text)
        spans: list[Span] = []
        for rule in self._rules:
            for match in rule.pattern.finditer(text):
                start, end = match.span()
                if start == end:
                    continue
                score = self._score(rule, match.group(0), folded, start, end)
                if score is None:
                    continue
                spans.append(
                    Span(
                        start=start,
                        end=end,
                        entity_type=rule.entity_type,
                        text=match.group(0),
                        score=round(score, 4),
                        source=self.name,
                    )
                )
        return spans

    def _score(
        self, rule: PatternRule, value: str, folded: str, start: int, end: int
    ) -> float | None:
        score = rule.base_score
        if rule.validator is not None:
            if rule.validator(value):
                score = max(score, rule.validated_score or score)
            elif rule.reject_invalid:
                return None

        before_start = max(0, start - self._before)
        after_end = min(len(folded), end + self._after)
        has_context = rule.context.search(folded, before_start, start) or rule.context.search(
            folded, end, after_end
        )
        if rule.require_context and not has_context:
            return None
        if has_context:
            score += rule.context_boost
        if rule.negative_context.search(folded, before_start, start):
            score -= rule.negative_penalty
        return min(1.0, max(0.0, score))
