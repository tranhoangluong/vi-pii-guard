"""Span-level evaluation with privacy-oriented leak metrics.

Besides standard precision/recall/F1, a redaction system must answer
"how much PII still reaches the LLM?". ``char_leak_rate`` counts gold PII
characters not covered by any prediction (label-agnostic), and
``entity_leak_rate`` counts gold entities with no covered character at all.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal

Triple = tuple[int, int, str]
MatchMode = Literal["exact", "overlap"]


@dataclass
class PRF:
    tp: int = 0
    fp: int = 0
    fn: int = 0

    @property
    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if self.tp + self.fp else 0.0

    @property
    def recall(self) -> float:
        return self.tp / (self.tp + self.fn) if self.tp + self.fn else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if p + r else 0.0

    def as_dict(self) -> dict[str, float | int]:
        return {
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1": round(self.f1, 4),
            "support": self.tp + self.fn,
            "tp": self.tp,
            "fp": self.fp,
            "fn": self.fn,
        }


@dataclass
class EvaluationReport:
    mode: MatchMode
    per_type: dict[str, PRF] = field(default_factory=dict)
    micro: PRF = field(default_factory=PRF)
    gold_chars: int = 0
    leaked_chars: int = 0
    gold_entities: int = 0
    leaked_entities: int = 0
    negative_docs: int = 0
    negative_docs_with_predictions: int = 0

    @property
    def macro_f1(self) -> float:
        scores = [prf.f1 for prf in self.per_type.values() if prf.tp + prf.fn]
        return sum(scores) / len(scores) if scores else 0.0

    @property
    def char_leak_rate(self) -> float:
        return self.leaked_chars / self.gold_chars if self.gold_chars else 0.0

    @property
    def entity_leak_rate(self) -> float:
        return self.leaked_entities / self.gold_entities if self.gold_entities else 0.0

    @property
    def negative_doc_fp_rate(self) -> float:
        return (
            self.negative_docs_with_predictions / self.negative_docs if self.negative_docs else 0.0
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "micro": self.micro.as_dict(),
            "macro_f1": round(self.macro_f1, 4),
            "char_leak_rate": round(self.char_leak_rate, 4),
            "entity_leak_rate": round(self.entity_leak_rate, 4),
            "negative_doc_fp_rate": round(self.negative_doc_fp_rate, 4),
            "per_type": {k: v.as_dict() for k, v in sorted(self.per_type.items())},
        }

    def to_markdown(self) -> str:
        lines = [
            f"Match mode: `{self.mode}`",
            "",
            "| Entity | Precision | Recall | F1 | Support |",
            "|---|---:|---:|---:|---:|",
        ]
        for label, prf in sorted(self.per_type.items()):
            lines.append(
                f"| {label} | {prf.precision:.3f} | {prf.recall:.3f} | {prf.f1:.3f} | {prf.tp + prf.fn} |"
            )
        lines.append(
            f"| **micro** | {self.micro.precision:.3f} | {self.micro.recall:.3f} | "
            f"{self.micro.f1:.3f} | {self.micro.tp + self.micro.fn} |"
        )
        lines += [
            "",
            f"- Macro F1: {self.macro_f1:.3f}",
            f"- Char leak rate: {self.char_leak_rate:.3%}",
            f"- Entity leak rate: {self.entity_leak_rate:.3%}",
            f"- Negative docs with a false positive: {self.negative_doc_fp_rate:.3%}",
        ]
        return "\n".join(lines)


def _matches(gold: Triple, pred: Triple, mode: MatchMode) -> bool:
    if gold[2] != pred[2]:
        return False
    if mode == "exact":
        return gold[0] == pred[0] and gold[1] == pred[1]
    return gold[0] < pred[1] and pred[0] < gold[1]


def evaluate(
    texts: Sequence[str],
    gold: Sequence[Sequence[Triple]],
    predicted: Sequence[Sequence[Triple]],
    *,
    mode: MatchMode = "exact",
) -> EvaluationReport:
    if not len(texts) == len(gold) == len(predicted):
        raise ValueError("texts, gold and predicted must have the same length")
    report = EvaluationReport(mode=mode)
    counts: dict[str, PRF] = defaultdict(PRF)

    for text, gold_spans, pred_spans in zip(texts, gold, predicted, strict=True):
        unmatched = list(pred_spans)
        for g in gold_spans:
            hit = next((p for p in unmatched if _matches(g, p, mode)), None)
            if hit is None:
                counts[g[2]].fn += 1
            else:
                counts[g[2]].tp += 1
                unmatched.remove(hit)
        for p in unmatched:
            counts[p[2]].fp += 1

        covered = {i for start, end, _ in pred_spans for i in range(start, end)}
        for start, end, _ in gold_spans:
            positions = [i for i in range(start, end) if not text[i].isspace()]
            leaked = [i for i in positions if i not in covered]
            report.gold_chars += len(positions)
            report.leaked_chars += len(leaked)
            report.gold_entities += 1
            report.leaked_entities += int(len(leaked) == len(positions))
        if not gold_spans:
            report.negative_docs += 1
            report.negative_docs_with_predictions += int(bool(pred_spans))

    report.per_type = dict(counts)
    for prf in counts.values():
        report.micro.tp += prf.tp
        report.micro.fp += prf.fp
        report.micro.fn += prf.fn
    return report
