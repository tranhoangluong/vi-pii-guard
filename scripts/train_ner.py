"""Fine-tune a token-classification model on synthetic (or hand-labeled) JSONL data.

    uv sync --extra train
    uv run python scripts/train_ner.py --train data/synthetic/train.jsonl \
        --dev data/synthetic/dev.jsonl --output models/xlmr-pii

The default backbone is ``xlm-roberta-base``: its fast tokenizer returns
character offsets on raw Vietnamese text. PhoBERT needs word-segmented input
(VnCoreNLP) first; see docs/adr/0004-ner-baseline-model.md.

The saved model uses our labels (B-PHONE, I-PERSON, ...), so it plugs
straight into ``Guard.default(ner_model="models/xlmr-pii")``.
"""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
from typing import Any

from vi_pii_guard.bio import bio_labels, bio_to_spans, spans_to_bio
from vi_pii_guard.domain import EntityType
from vi_pii_guard.metrics import evaluate
from vi_pii_guard.synth import Example


def load(path: Path) -> list[Example]:
    return [Example.from_json(line) for line in path.read_text("utf-8").splitlines() if line]


def encode(
    examples: list[Example], tokenizer: Any, label2id: dict[str, int], max_length: int
) -> tuple[list[dict[str, list[int]]], list[list[tuple[int, int]]]]:
    features: list[dict[str, list[int]]] = []
    all_offsets: list[list[tuple[int, int]]] = []
    for example in examples:
        encoded = tokenizer(
            example.text, truncation=True, max_length=max_length, return_offsets_mapping=True
        )
        offsets = [tuple(o) for o in encoded.pop("offset_mapping")]
        tags = spans_to_bio(offsets, [(s.start, s.end, s.label) for s in example.spans])
        encoded["labels"] = [-100 if t is None else label2id[t] for t in tags]
        features.append(dict(encoded))
        all_offsets.append(offsets)
    return features, all_offsets


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train", type=Path, required=True)
    parser.add_argument("--dev", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("models/xlmr-pii"))
    parser.add_argument("--model", default="xlm-roberta-base")
    parser.add_argument("--epochs", type=float, default=3.0)
    parser.add_argument("--lr", type=float, default=3e-5)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--max-length", type=int, default=256)
    parser.add_argument("--seed", type=int, default=13)
    args = parser.parse_args()

    import numpy as np
    from transformers import (
        AutoModelForTokenClassification,
        AutoTokenizer,
        DataCollatorForTokenClassification,
        Trainer,
        TrainingArguments,
    )

    labels = bio_labels(tuple(EntityType))
    label2id = {label: i for i, label in enumerate(labels)}
    id2label = dict(enumerate(labels))

    tokenizer = AutoTokenizer.from_pretrained(args.model, use_fast=True)
    train_examples, dev_examples = load(args.train), load(args.dev)
    train_features, _ = encode(train_examples, tokenizer, label2id, args.max_length)
    dev_features, dev_offsets = encode(dev_examples, tokenizer, label2id, args.max_length)

    model = AutoModelForTokenClassification.from_pretrained(
        args.model, num_labels=len(labels), id2label=id2label, label2id=label2id
    )

    def compute_metrics(eval_pred: Any) -> dict[str, float]:
        logits, label_ids = eval_pred
        predictions = np.argmax(logits, axis=-1)
        texts, gold, predicted = [], [], []
        for i, example in enumerate(dev_examples):
            offsets = dev_offsets[i]
            tags = [
                None if label_ids[i][j] == -100 else id2label[int(predictions[i][j])]
                for j in range(len(offsets))
            ]
            texts.append(example.text)
            gold.append([(s.start, s.end, s.label) for s in example.spans])
            predicted.append(bio_to_spans(offsets, tags))
        report = evaluate(texts, gold, predicted, mode="exact")
        return {
            "precision": report.micro.precision,
            "recall": report.micro.recall,
            "f1": report.micro.f1,
            "macro_f1": report.macro_f1,
            "char_leak_rate": evaluate(texts, gold, predicted, mode="overlap").char_leak_rate,
        }

    report_to = ["mlflow"] if importlib.util.find_spec("mlflow") else []
    training_args = TrainingArguments(
        output_dir=str(args.output / "checkpoints"),
        learning_rate=args.lr,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        num_train_epochs=args.epochs,
        weight_decay=0.01,
        warmup_ratio=0.1,
        eval_strategy="epoch",
        save_strategy="epoch",
        save_total_limit=2,
        load_best_model_at_end=True,
        metric_for_best_model="f1",
        logging_steps=50,
        seed=args.seed,
        report_to=report_to,
    )
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_features,
        eval_dataset=dev_features,
        data_collator=DataCollatorForTokenClassification(tokenizer),
        compute_metrics=compute_metrics,
    )
    trainer.train()
    print(trainer.evaluate())
    trainer.save_model(str(args.output))
    tokenizer.save_pretrained(str(args.output))
    print(f"saved to {args.output}")


if __name__ == "__main__":
    main()
