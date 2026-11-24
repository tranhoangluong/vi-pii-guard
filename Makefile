.PHONY: install lint format typecheck test check data eval serve docker

install:
	uv sync --extra api --group dev

lint:
	uv run ruff check .

format:
	uv run ruff format .

typecheck:
	uv run mypy

test:
	uv run pytest --cov --cov-report=term-missing

check:
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy
	uv run pytest

data:
	uv run python scripts/generate_data.py --out data/synthetic

eval: data
	uv run python scripts/evaluate.py --data data/synthetic/test.jsonl --name rules

serve:
	uv run vi-pii-guard serve --host 0.0.0.0 --port 8000

docker:
	docker build -t vi-pii-guard:dev .
