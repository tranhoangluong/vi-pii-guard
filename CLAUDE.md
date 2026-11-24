# CLAUDE.md

Guidance for AI coding agents (Claude Code, Codex) working in this repository.

## Project

`vi-pii-guard` detects Vietnamese PII, replaces it with reversible placeholders before text is
sent to an LLM, and restores the answer. It is also the codebase of a master's thesis, so
experiments must be reproducible and metrics honest.

## Commands

```bash
uv sync --extra api --group dev          # install
make check                               # ruff + format check + mypy --strict + pytest
uv run pytest tests/test_recognizers.py  # one file
uv run vi-pii-guard serve                # API on :8000
uv run python scripts/generate_data.py   # synthetic data -> data/synthetic
uv run python scripts/evaluate.py --data data/synthetic/test.jsonl --name rules
```

Training needs `uv sync --extra train` and ideally a GPU.

## Architecture (ports and adapters)

- `domain.py`: `EntityType`, `Span`, `Recognizer` port. No I/O, no third-party imports.
- `recognizers/`: adapters. `rules.py` holds the regex rules and scores, `names.py` and
  `address.py` are rule baselines, `ner.py` wraps Hugging Face models.
- `validators.py`: pure functions for Vietnamese identifiers (CCCD, tax code, phone, Luhn, dates).
- `guard.py`: application service (`detect`, `redact`, `restore`, `forget`).
- `vault.py`: `Vault` port + `InMemoryVault`.
- `api/`: FastAPI delivery layer only. Business logic stays in `Guard`.
- `synth/`, `metrics.py`, `bio.py`: research tooling, dependency-free.
- `scripts/`: thin CLIs for data generation, training and evaluation.

Decisions are in `docs/adr/`. Read the relevant ADR before changing behaviour it covers.

## Rules

- **Never write real personal data** anywhere: code, tests, fixtures, docs, commit messages.
  Use generated or obviously fake values.
- **Never log message content or PII.** Log counts, types and status codes only.
- All offsets refer to NFC-normalized text. Normalize before slicing.
- The core package must keep zero runtime dependencies. New heavy deps go into an extra.
- Every new rule or validator needs tests for a positive case, a negative case and at least
  one hard negative (a value that looks similar but is not PII).
- Changing rule scores changes the metrics: rerun `scripts/evaluate.py` and mention the
  before/after numbers in the PR.
- Code identifiers and docs in English; `docs/research/` is in Vietnamese.
- `mypy --strict` must pass. Prefer small pure functions over new classes.
- Commits: `<Scope>: <description>`, for example `Recognizers: add VIN rule`.

## Definition of done

`make check` passes, docs/ADR updated if behaviour changed, no real data added.
