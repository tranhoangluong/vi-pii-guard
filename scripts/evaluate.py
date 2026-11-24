"""Evaluate the guard on a labeled JSONL file and write a report.

    uv run python scripts/evaluate.py --data data/synthetic/test.jsonl --name rules
    uv run python scripts/evaluate.py --data data/synthetic/test.jsonl \
        --ner-model models/xlmr-pii --name hybrid --mlflow
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path

from vi_pii_guard import Guard, normalize
from vi_pii_guard.domain import EntityType
from vi_pii_guard.metrics import Triple, evaluate
from vi_pii_guard.synth import Example


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, round(q * (len(ordered) - 1)))
    return ordered[index]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--ner-model")
    parser.add_argument("--min-score", type=float, default=0.5)
    parser.add_argument("--name", default="run")
    parser.add_argument("--report-dir", type=Path, default=Path("reports"))
    parser.add_argument("--mlflow", action="store_true", help="log metrics to MLflow")
    args = parser.parse_args()

    examples = [
        Example.from_json(line) for line in args.data.read_text("utf-8").splitlines() if line
    ]
    guard = Guard.default(ner_model=args.ner_model, min_score=args.min_score)

    texts: list[str] = []
    gold: list[list[Triple]] = []
    predicted: list[list[Triple]] = []
    latencies_ms: list[float] = []
    for example in examples:
        if normalize(example.text) != example.text:
            raise SystemExit(f"{example.id}: text is not NFC-normalized; offsets would drift")
        started = time.perf_counter()
        spans = guard.detect(example.text)
        latencies_ms.append((time.perf_counter() - started) * 1000)
        texts.append(example.text)
        gold.append([(s.start, s.end, s.label) for s in example.spans])
        predicted.append([(s.start, s.end, s.entity_type.value) for s in spans])

    exact = evaluate(texts, gold, predicted, mode="exact")
    overlap = evaluate(texts, gold, predicted, mode="overlap")
    latency = {
        "p50_ms": round(statistics.median(latencies_ms), 3),
        "p95_ms": round(percentile(latencies_ms, 0.95), 3),
        "mean_ms": round(statistics.fmean(latencies_ms), 3),
    }
    report = {
        "name": args.name,
        "data": str(args.data),
        "examples": len(examples),
        "recognizers": list(guard.recognizer_names),
        "ner_model": args.ner_model,
        "min_score": args.min_score,
        "exact": exact.as_dict(),
        "overlap": overlap.as_dict(),
        "latency": latency,
    }

    args.report_dir.mkdir(parents=True, exist_ok=True)
    (args.report_dir / f"{args.name}.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    markdown = (
        f"# {args.name}\n\nData: `{args.data}` ({len(examples)} examples)\n\n"
        f"## Exact match\n\n{exact.to_markdown()}\n\n## Overlap match\n\n{overlap.to_markdown()}\n\n"
        f"## Latency\n\np50 {latency['p50_ms']} ms, p95 {latency['p95_ms']} ms per text\n"
    )
    (args.report_dir / f"{args.name}.md").write_text(markdown, encoding="utf-8")
    print(markdown)

    if args.mlflow:
        import mlflow

        with mlflow.start_run(run_name=args.name):
            mlflow.log_params(
                {
                    "data": str(args.data),
                    "ner_model": args.ner_model or "none",
                    "min_score": args.min_score,
                }
            )
            mlflow.log_metrics(
                {
                    "exact_micro_f1": exact.micro.f1,
                    "overlap_micro_f1": overlap.micro.f1,
                    "char_leak_rate": overlap.char_leak_rate,
                    "entity_leak_rate": overlap.entity_leak_rate,
                    "latency_p95_ms": latency["p95_ms"],
                    **{f"f1_{label}": prf.f1 for label, prf in exact.per_type.items()},
                }
            )
            mlflow.log_artifact(str(args.report_dir / f"{args.name}.json"))

    known = {e.value for e in EntityType}
    unknown = {label for spans in gold for _, _, label in spans} - known
    if unknown:
        print(f"warning: gold labels not in EntityType: {sorted(unknown)}")


if __name__ == "__main__":
    main()
