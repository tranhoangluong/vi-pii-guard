"""Generate synthetic train/dev/test splits plus address-format drift test sets.

uv run python scripts/generate_data.py --out data/synthetic --train 8000 --dev 1000 --test 1000
"""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from vi_pii_guard.synth import SyntheticGenerator


def write(path: Path, generator: SyntheticGenerator, n: int, negative_ratio: float) -> Counter[str]:
    path.parent.mkdir(parents=True, exist_ok=True)
    labels: Counter[str] = Counter()
    with path.open("w", encoding="utf-8") as handle:
        for example in generator.generate(n, negative_ratio=negative_ratio):
            handle.write(example.to_json() + "\n")
            labels.update(span.label for span in example.spans)
    return labels


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("data/synthetic"))
    parser.add_argument("--train", type=int, default=8000)
    parser.add_argument("--dev", type=int, default=1000)
    parser.add_argument("--test", type=int, default=1000)
    parser.add_argument("--negative-ratio", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=13)
    parser.add_argument(
        "--train-address-format",
        choices=["pre_2025", "post_2025", "mixed"],
        default="mixed",
        help="use pre_2025 to simulate a model trained before the 2025 address reform",
    )
    args = parser.parse_args()

    # Different seeds per split so the same values do not leak across splits.
    splits = {
        "train.jsonl": (SyntheticGenerator(args.seed, args.train_address_format), args.train),
        "dev.jsonl": (SyntheticGenerator(args.seed + 1, "mixed"), args.dev),
        "test.jsonl": (SyntheticGenerator(args.seed + 2, "mixed"), args.test),
        "test_pre_2025.jsonl": (SyntheticGenerator(args.seed + 3, "pre_2025"), args.test),
        "test_post_2025.jsonl": (SyntheticGenerator(args.seed + 4, "post_2025"), args.test),
    }
    for name, (generator, n) in splits.items():
        labels = write(args.out / name, generator, n, args.negative_ratio)
        print(f"{name:<22} {n:>6} examples  {dict(sorted(labels.items()))}")


if __name__ == "__main__":
    main()
