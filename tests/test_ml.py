"""Tests for the dependency-free ML helpers: synthetic data, BIO tags, metrics, NER adapter."""

from typing import Any

import pytest

from vi_pii_guard import EntityType
from vi_pii_guard.bio import bio_labels, bio_to_spans, spans_to_bio
from vi_pii_guard.metrics import evaluate
from vi_pii_guard.recognizers.ner import TransformersNerRecognizer
from vi_pii_guard.synth import Example, SyntheticGenerator
from vi_pii_guard.validators import (
    is_valid_mobile,
    is_valid_national_id,
    is_valid_tax_code,
    luhn_ok,
)


def test_synthetic_spans_align_and_are_deterministic() -> None:
    first = list(SyntheticGenerator(seed=1).generate(300))
    second = list(SyntheticGenerator(seed=1).generate(300))
    assert [e.text for e in first] == [e.text for e in second]
    labels = set()
    for example in first:
        for span in example.spans:
            value = example.text[span.start : span.end]
            assert value == value.strip()
            assert value
            labels.add(span.label)
    assert labels == {e.value for e in EntityType}
    assert any(not e.spans for e in first)  # hard negatives present


def test_synthetic_values_are_structurally_valid() -> None:
    generator = SyntheticGenerator(seed=7)
    for _ in range(200):
        assert is_valid_mobile(generator.phone())
        assert is_valid_national_id(generator.national_id())
        assert is_valid_tax_code(generator.tax_code())
        assert luhn_ok(generator.card_number())


def test_example_json_round_trip() -> None:
    example = next(SyntheticGenerator(seed=3).generate(1, negative_ratio=0.0))
    assert Example.from_json(example.to_json()) == example


def test_address_format_is_controllable() -> None:
    post = SyntheticGenerator(seed=5, address_format="post_2025")
    pre = SyntheticGenerator(seed=5, address_format="pre_2025")
    assert all("quận" not in post.address() and "huyện" not in post.address() for _ in range(50))
    assert any("quận" in pre.address() or "huyện" in pre.address() for _ in range(50))


def test_bio_round_trip() -> None:
    text = "Gọi Nguyễn Văn An số 0912345678"
    offsets = [(0, 0), (0, 3), (4, 10), (11, 14), (15, 17), (18, 20), (21, 31), (0, 0)]
    spans = [(4, 17, "PERSON"), (21, 31, "PHONE")]
    tags = spans_to_bio(offsets, spans)
    assert tags == [None, "O", "B-PERSON", "I-PERSON", "I-PERSON", "O", "B-PHONE", None]
    assert bio_to_spans(offsets, tags) == spans
    assert text[4:17] == "Nguyễn Văn An"
    assert text[21:31] == "0912345678"
    assert len(bio_labels()) == 1 + 2 * len(EntityType)


def test_metrics_exact_overlap_and_leak() -> None:
    texts = ["Gọi An số 0912345678", "Không có gì"]
    gold = [[(4, 6, "PERSON"), (10, 20, "PHONE")], []]
    pred = [[(10, 18, "PHONE")], [(0, 5, "PERSON")]]
    exact = evaluate(texts, gold, pred, mode="exact")
    overlap = evaluate(texts, gold, pred, mode="overlap")
    assert exact.micro.tp == 0
    assert overlap.micro.tp == 1
    assert overlap.per_type["PERSON"].fn == 1
    assert overlap.leaked_chars == 4  # "An" + last two digits
    assert overlap.entity_leak_rate == pytest.approx(0.5)
    assert overlap.negative_doc_fp_rate == 1.0


def test_ner_adapter_maps_labels_and_chunk_offsets() -> None:
    text = "x" * 20 + " Trần An "

    def fake_pipeline(chunk: str) -> list[dict[str, Any]]:
        index = chunk.find("Trần An")
        if index < 0:
            return []
        return [
            {"entity_group": "PER", "score": 0.97, "start": index - 1, "end": index + 8},
            {"entity_group": "LOC", "score": 0.9, "start": 0, "end": 1},
        ]

    recognizer = TransformersNerRecognizer(pipeline=fake_pipeline, max_chars=25, overlap_chars=10)
    spans = recognizer.recognize(text)
    assert {(s.entity_type, s.text) for s in spans} == {(EntityType.PERSON, "Trần An")}
    assert all(text[s.start : s.end] == s.text for s in spans)


def test_ner_adapter_requires_model_or_pipeline() -> None:
    with pytest.raises(ValueError, match="model"):
        TransformersNerRecognizer()
