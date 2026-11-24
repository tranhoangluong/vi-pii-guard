"""Command line interface: ``vi-pii-guard detect|redact|serve``."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from vi_pii_guard import __version__
from vi_pii_guard.domain import EntityType
from vi_pii_guard.guard import Guard


def _read_text(value: str) -> str:
    return sys.stdin.read() if value == "-" else value


def _build_guard(args: argparse.Namespace) -> Guard:
    entities = [EntityType(e) for e in args.entities.split(",")] if args.entities else None
    return Guard.default(ner_model=args.ner_model, min_score=args.min_score, entities=entities)


def _cmd_detect(args: argparse.Namespace) -> int:
    guard = _build_guard(args)
    spans = guard.detect(_read_text(args.text))
    if args.json:
        payload = [
            {
                "start": s.start,
                "end": s.end,
                "entity_type": s.entity_type.value,
                "text": s.text,
                "score": s.score,
                "source": s.source,
            }
            for s in spans
        ]
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for s in spans:
            print(f"{s.entity_type.value:<14} {s.score:.2f}  [{s.start}:{s.end}]  {s.text}")
    return 0


def _cmd_redact(args: argparse.Namespace) -> int:
    guard = _build_guard(args)
    result = guard.redact(_read_text(args.text), strategy=args.strategy)
    if args.json:
        payload = {
            "text": result.text,
            "session_id": result.session_id,
            "entities": [
                {
                    "replacement": item.replacement,
                    "entity_type": item.span.entity_type.value,
                    "original": item.span.text,
                }
                for item in result.items
            ],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(result.text, end="" if result.text.endswith("\n") else "\n")
    return 0


def _cmd_serve(args: argparse.Namespace) -> int:
    try:
        import uvicorn
    except ImportError:
        print("The API needs the `api` extra: uv sync --extra api", file=sys.stderr)
        return 1
    uvicorn.run("vi_pii_guard.api.app:create_app", factory=True, host=args.host, port=args.port)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vi-pii-guard", description="Detect and redact Vietnamese PII."
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common(p: argparse.ArgumentParser) -> None:
        p.add_argument("text", help="text to scan, or '-' to read from stdin")
        p.add_argument(
            "--ner-model", help="Hugging Face model id or local path (needs `ner` extra)"
        )
        p.add_argument("--min-score", type=float, default=0.5)
        p.add_argument("--entities", help="comma-separated subset, e.g. PHONE,EMAIL")
        p.add_argument("--json", action="store_true", help="print JSON")

    detect = sub.add_parser("detect", help="list detected PII spans")
    add_common(detect)
    detect.set_defaults(func=_cmd_detect)

    redact = sub.add_parser("redact", help="print the text with PII replaced")
    add_common(redact)
    redact.add_argument("--strategy", choices=["placeholder", "mask"], default="placeholder")
    redact.set_defaults(func=_cmd_redact)

    serve = sub.add_parser("serve", help="run the HTTP API and LLM proxy")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    serve.set_defaults(func=_cmd_serve)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    code: int = args.func(args)
    return code


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
