"""Detection adapters. Each one implements :class:`vi_pii_guard.domain.Recognizer`."""

from vi_pii_guard.domain import Recognizer
from vi_pii_guard.recognizers.address import TriggerAddressRecognizer
from vi_pii_guard.recognizers.names import TriggerNameRecognizer
from vi_pii_guard.recognizers.patterns import PatternRecognizer, PatternRule
from vi_pii_guard.recognizers.rules import default_pattern_recognizer, default_rules


def default_recognizers() -> list[Recognizer]:
    """Rule-only recognizers that need no model download."""
    return [default_pattern_recognizer(), TriggerNameRecognizer(), TriggerAddressRecognizer()]


__all__ = [
    "PatternRecognizer",
    "PatternRule",
    "TriggerAddressRecognizer",
    "TriggerNameRecognizer",
    "default_recognizers",
    "default_rules",
]
