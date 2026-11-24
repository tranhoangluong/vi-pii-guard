"""Synthetic Vietnamese PII data for training and evaluation."""

from vi_pii_guard.synth.generator import (
    NEGATIVE_TEMPLATES,
    TEMPLATES,
    Example,
    GoldSpan,
    SyntheticGenerator,
)

__all__ = ["NEGATIVE_TEMPLATES", "TEMPLATES", "Example", "GoldSpan", "SyntheticGenerator"]
