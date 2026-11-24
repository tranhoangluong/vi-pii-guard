"""Vietnamese PII detection and reversible redaction for LLM pipelines."""

from vi_pii_guard.domain import EntityType, Recognizer, Span
from vi_pii_guard.guard import Guard, RedactedItem, RedactionResult
from vi_pii_guard.normalize import normalize

__version__ = "0.1.0"

__all__ = [
    "EntityType",
    "Guard",
    "Recognizer",
    "RedactedItem",
    "RedactionResult",
    "Span",
    "__version__",
    "normalize",
]
