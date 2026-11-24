# ADR-0001: Hybrid detection with ports and adapters

- Status: accepted
- Date: 2026-11-23

## Context

Vietnamese PII falls into two groups. Structured identifiers (phone, CCCD, tax code, card,
plate) have fixed formats and often a checksum. Names and addresses have no format; recognizing
them needs a learned model. A pure-ML approach wastes model capacity on what a regex does
exactly, and is hard to audit. A pure-rule approach misses names typed without capitals or
without a trigger phrase.

## Decision

- Every detector implements one port, `Recognizer.recognize(text) -> list[Span]`.
- Built-in adapters: `PatternRecognizer` (regex + validator + context scoring),
  `TriggerNameRecognizer`, `TriggerAddressRecognizer` (rule baselines) and
  `TransformersNerRecognizer` (any Hugging Face token-classification model).
- `Guard` (application service) runs all recognizers on the NFC-normalized text, drops spans
  below `min_score`, then keeps a non-overlapping subset ordered by score, then length.
- Scores are calibrated by hand for rules (`base`, `validated`, `+context`, `-negative context`)
  so that a structurally valid value passes on its own, and an ambiguous value only passes with
  context.
- The core package has no third-party dependencies. FastAPI and transformers live behind the
  `api` and `ner` extras.

## Consequences

- Rules and the model can be evaluated separately and together, which is the comparison the
  research needs.
- Rule scores and model probabilities share one scale without calibration. If the model
  over-predicts, a per-recognizer weight or threshold is the next step.
- Adding an entity type means adding an `EntityType` member, a rule or training data, and tests.
