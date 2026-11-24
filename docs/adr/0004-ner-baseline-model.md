# ADR-0004: XLM-RoBERTa as the first NER backbone

- Status: accepted
- Date: 2026-11-23

## Context

The training script needs character offsets from the tokenizer to turn character-level labels
into token labels. Candidates: PhoBERT (Vietnamese monolingual), XLM-RoBERTa (multilingual) and
multilingual encoders such as mDeBERTa.

## Decision

Use `xlm-roberta-base` as the default backbone. Its fast tokenizer returns offsets on raw
Vietnamese text, so no extra preprocessing is required.

PhoBERT was pre-trained on word-segmented text (for example segmented with VnCoreNLP, which
needs Java), so inputs must be segmented the same way and labels mapped through that step. It
stays an experiment for the thesis, not the default.

## Consequences

- One training pipeline works on raw text; any Hugging Face encoder with a fast tokenizer can be
  swapped in with `--model`.
- Comparing PhoBERT against XLM-R requires a segmentation step and an offset mapping back to
  the original text.
