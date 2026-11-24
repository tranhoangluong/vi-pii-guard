"""Adapter for Hugging Face token-classification models.

Requires the ``ner`` extra (``transformers`` + ``torch``). The pipeline can be
injected, which keeps this adapter testable without downloading a model.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from vi_pii_guard.domain import EntityType, Span

NerPipeline = Callable[[str], list[dict[str, Any]]]

# Common label names from public NER models mapped onto our taxonomy.
# Generic LOC/ORG are intentionally not mapped: a location is not always PII.
DEFAULT_LABEL_MAP: Mapping[str, EntityType] = {
    **{entity.value: entity for entity in EntityType},
    "PER": EntityType.PERSON,
    "PATIENT": EntityType.PERSON,
    "NAME": EntityType.PERSON,
    "ADDR": EntityType.ADDRESS,
    "PHONE_NUMBER": EntityType.PHONE,
    "ID": EntityType.NATIONAL_ID,
}


class TransformersNerRecognizer:
    """Runs a token-classification model and maps its labels to :class:`EntityType`."""

    name = "ner"

    def __init__(
        self,
        model: str | None = None,
        *,
        pipeline: NerPipeline | None = None,
        label_map: Mapping[str, EntityType] | None = None,
        device: int | str = -1,
        max_chars: int = 1500,
        overlap_chars: int = 200,
    ) -> None:
        if pipeline is None and model is None:
            raise ValueError("either `model` or `pipeline` is required")
        if overlap_chars >= max_chars:
            raise ValueError("overlap_chars must be smaller than max_chars")
        self._pipeline = pipeline or _load_pipeline(model or "", device)
        self._label_map = dict(label_map or DEFAULT_LABEL_MAP)
        self._max_chars = max_chars
        self._overlap = overlap_chars
        self.model_name = model

    def recognize(self, text: str) -> list[Span]:
        spans: list[Span] = []
        for offset, chunk in self._chunks(text):
            for entity in self._pipeline(chunk):
                span = self._to_span(entity, offset, text)
                if span is not None:
                    spans.append(span)
        return spans

    def _chunks(self, text: str) -> list[tuple[int, str]]:
        if len(text) <= self._max_chars:
            return [(0, text)]
        step = self._max_chars - self._overlap
        return [
            (start, text[start : start + self._max_chars]) for start in range(0, len(text), step)
        ]

    def _to_span(self, entity: Mapping[str, Any], offset: int, text: str) -> Span | None:
        raw_label = str(entity.get("entity_group") or entity.get("entity") or "")
        label = raw_label.split("-", 1)[1] if raw_label[:2] in ("B-", "I-") else raw_label
        entity_type = self._label_map.get(label.upper())
        start, end = entity.get("start"), entity.get("end")
        if entity_type is None or start is None or end is None:
            return None
        start, end = int(start) + offset, int(end) + offset
        while start < end and text[start].isspace():
            start += 1
        while end > start and text[end - 1].isspace():
            end -= 1
        if start >= end:
            return None
        score = min(1.0, max(0.0, float(entity.get("score", 0.0))))
        return Span(start, end, entity_type, text[start:end], score, self.name)


def _load_pipeline(model: str, device: int | str) -> NerPipeline:
    try:
        from transformers import pipeline
    except ImportError as exc:  # pragma: no cover - depends on optional extra
        raise ImportError(
            "NER support needs the `ner` extra: uv sync --extra ner (or pip install 'vi-pii-guard[ner]')"
        ) from exc
    ner: NerPipeline = pipeline(
        "token-classification", model=model, aggregation_strategy="simple", device=device
    )
    return ner
