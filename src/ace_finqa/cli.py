"""Command-line interface for the dependency-free ACE-FinQA core."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from . import __version__
from .artifacts import verify_repository
from .data import DatasetError, summarize_data_dir
from .evaluation import EvaluationError, evaluate_files


def _add_pretty_option(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Indent JSON output for people instead of emitting compact JSON.",
    )


def build_parser() -> argparse.ArgumentParser:
    """Build the public argparse tree (also useful for documentation tests)."""

    parser = argparse.ArgumentParser(
        prog="ace-finqa",
        description="CPU-safe FinQA data, evaluation, and artifact tools.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)

    data_summary = commands.add_parser(
        "data-summary",
        help="Validate and summarize canonical train/dev/test splits.",
    )
    data_summary.add_argument(
        "data_dir",
        nargs="?",
        default=None,
        help="Directory containing train.json, dev.json, and test.json.",
    )
    data_summary.add_argument(
        "--data-dir",
        dest="data_dir_option",
        help="Explicit alias for the optional data directory argument.",
    )
    data_summary.add_argument(
        "--no-enforce-size",
        action="store_true",
        help="Allow fixture-sized splits instead of requiring canonical FinQA counts.",
    )
    _add_pretty_option(data_summary)

    evaluate = commands.add_parser(
        "evaluate",
        help="Recompute strict-v1 EA/PA metrics from model predictions.",
    )
    evaluate.add_argument(
        "dataset",
        nargs="?",
        help="FinQA split JSON. May also be supplied with --data.",
    )
    evaluate.add_argument(
        "--data",
        "--data-file",
        dest="data_option",
        help="FinQA split JSON (explicit alias for the optional positional argument).",
    )
    evaluate.add_argument(
        "--predictions",
        required=True,
        help="Prediction records in JSON, JSONL, or CSV format.",
    )
    evaluate.add_argument(
        "--allow-partial",
        action="store_true",
        help="Evaluate an explicitly partial index set and report coverage.",
    )
    evaluate.add_argument(
        "--include-details",
        action="store_true",
        help="Include per-record programs, values, errors, and outcomes.",
    )
    evaluate.add_argument(
        "--output",
        help="Write the JSON report atomically to this path as well as stdout.",
    )
    _add_pretty_option(evaluate)

    verify = commands.add_parser(
        "verify-repo",
        help="Validate data and cross-check structured result artifacts.",
    )
    verify.add_argument(
        "root",
        nargs="?",
        default=".",
        help="Repository root (defaults to the current directory).",
    )
    verify.add_argument(
        "--data-dir",
        help="Dataset directory, resolved relative to root unless absolute.",
    )
    verify.add_argument(
        "--results-dir",
        help="Result artifact directory, resolved relative to root unless absolute.",
    )
    _add_pretty_option(verify)
    return parser


def _encode(payload: Any, *, pretty: bool) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        indent=2 if pretty else None,
        separators=None if pretty else (",", ":"),
        sort_keys=True,
    )


def _write_atomic(path: str | Path, content: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.tmp")
    try:
        temporary.write_text(content + "\n", encoding="utf-8")
        temporary.replace(target)
    finally:
        if temporary.exists():
            temporary.unlink()


def _dataset_argument(args: argparse.Namespace) -> str:
    positional = args.dataset
    option = args.data_option
    if positional and option and Path(positional) != Path(option):
        raise EvaluationError(
            "Dataset was supplied twice with different values; use either the positional "
            "argument or --data."
        )
    value = option or positional
    if not value:
        raise EvaluationError("evaluate requires a dataset path (positional or --data)")
    return str(value)


def _data_directory_argument(args: argparse.Namespace) -> str:
    positional = args.data_dir
    option = args.data_dir_option
    if positional and option and Path(positional) != Path(option):
        raise EvaluationError(
            "Data directory was supplied twice with different values; use either the "
            "positional argument or --data-dir."
        )
    return str(option or positional or "data/finqa")


def _run(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    if args.command == "data-summary":
        payload = summarize_data_dir(
            _data_directory_argument(args),
            enforce_expected_size=not args.no_enforce_size,
        )
        return payload, 0 if payload["ok"] else 1
    if args.command == "verify-repo":
        report = verify_repository(
            args.root,
            data_dir=args.data_dir,
            results_dir=args.results_dir,
        )
        return report.to_dict(), 0 if report.ok else 1
    if args.command == "evaluate":
        report = evaluate_files(
            _dataset_argument(args),
            args.predictions,
            require_complete=not args.allow_partial,
        )
        payload = report.to_dict(include_details=args.include_details)
        return payload, 0
    raise EvaluationError(f"Unknown command: {args.command}")


def main(argv: Sequence[str] | None = None) -> int:
    """Run a CLI command and return a process-style exit code."""

    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        payload, exit_code = _run(args)
        content = _encode(payload, pretty=args.pretty)
        if getattr(args, "output", None):
            _write_atomic(args.output, content)
        print(content)
        return exit_code
    except (DatasetError, EvaluationError, OSError, UnicodeError, ValueError) as exc:
        error = {
            "schema": "ace-finqa.cli-error.v1",
            "ok": False,
            "error": type(exc).__name__,
            "message": str(exc),
        }
        print(_encode(error, pretty=getattr(args, "pretty", False)), file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover - exercised by python -m ace_finqa
    raise SystemExit(main())
