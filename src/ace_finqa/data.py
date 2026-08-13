"""FinQA dataset loading, validation, and dependency-free summaries."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

EXPECTED_FINQA_SPLIT_SIZES: dict[str, int] = {
    "train": 6251,
    "dev": 883,
    "test": 1147,
}

_OPERATION_RE = re.compile(
    r"\b(add|subtract|multiply|divide|greater|exp|table_(?:max|min|average|sum))\s*\(",
    re.IGNORECASE,
)


class DatasetError(ValueError):
    """Raised when a dataset file cannot be loaded as a FinQA split."""


@dataclass(frozen=True)
class ValidationIssue:
    """One actionable dataset validation finding."""

    code: str
    message: str
    index: int | None = None
    severity: str = "error"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DatasetValidation:
    """Validation result for one FinQA split."""

    split: str | None
    sample_count: int
    valid_count: int
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)

    def to_dict(self) -> dict[str, Any]:
        return {
            "split": self.split,
            "sample_count": self.sample_count,
            "valid_count": self.valid_count,
            "ok": self.ok,
            "issues": [issue.to_dict() for issue in self.issues],
        }


@dataclass(frozen=True)
class SplitSummary:
    """Stable, JSON-serializable summary of one dataset split."""

    split: str | None
    path: str | None
    sha256: str | None
    samples: int
    valid_programs: int
    numeric_answers: int
    string_answers: int
    missing_answers: int
    operation_counts: Mapping[str, int]
    program_steps: Mapping[str, int]
    validation_ok: bool
    issue_count: int

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["operation_counts"] = dict(self.operation_counts)
        value["program_steps"] = dict(self.program_steps)
        return value


def sha256_file(path: str | Path, *, chunk_size: int = 1024 * 1024) -> str:
    """Return a content digest without loading a potentially large split twice."""

    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_split(path: str | Path) -> list[dict[str, Any]]:
    """Load a FinQA split and reject non-array or non-object payloads."""

    source = Path(path)
    try:
        with source.open("r", encoding="utf-8") as stream:
            payload = json.load(stream)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DatasetError(f"Could not load FinQA split {source}: {exc}") from exc
    if not isinstance(payload, list):
        raise DatasetError(f"FinQA split must be a JSON array: {source}")
    if not all(isinstance(sample, dict) for sample in payload):
        raise DatasetError(f"Every FinQA sample must be a JSON object: {source}")
    return payload


def _is_string_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _is_table(value: Any) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and all(
            isinstance(row, list) and all(isinstance(cell, str) for cell in row) for row in value
        )
    )


def validate_samples(
    samples: Sequence[Mapping[str, Any]],
    *,
    split: str | None = None,
    enforce_expected_size: bool = False,
) -> DatasetValidation:
    """Validate fields used by the CPU-safe reasoning pipeline.

    Validation deliberately checks the local preprocessed FinQA schema, not just
    whether the JSON parses. Size checks are opt-in so small fixtures remain useful.
    """

    issues: list[ValidationIssue] = []
    valid_count = 0
    seen_ids: set[str] = set()

    if split is not None and split not in EXPECTED_FINQA_SPLIT_SIZES:
        issues.append(ValidationIssue("unknown_split", f"Unknown FinQA split: {split}"))
    if enforce_expected_size and split in EXPECTED_FINQA_SPLIT_SIZES:
        expected = EXPECTED_FINQA_SPLIT_SIZES[split]
        if len(samples) != expected:
            issues.append(
                ValidationIssue(
                    "unexpected_split_size",
                    f"{split} has {len(samples)} samples; expected {expected}",
                )
            )

    for index, sample in enumerate(samples):
        sample_ok = True
        qa = sample.get("qa")
        if not isinstance(qa, Mapping):
            issues.append(ValidationIssue("missing_qa", "qa must be an object", index))
            continue
        question = qa.get("question")
        program = qa.get("program")
        if not isinstance(question, str) or not question.strip():
            issues.append(ValidationIssue("invalid_question", "qa.question is required", index))
            sample_ok = False
        if not isinstance(program, str) or not program.strip():
            issues.append(ValidationIssue("invalid_program", "qa.program is required", index))
            sample_ok = False
        if "exe_ans" not in qa:
            issues.append(ValidationIssue("missing_answer", "qa.exe_ans is required", index))
            sample_ok = False
        gold_inds = qa.get("gold_inds")
        if gold_inds is not None and not isinstance(gold_inds, Mapping):
            issues.append(
                ValidationIssue("invalid_gold_inds", "qa.gold_inds must be an object", index)
            )
            sample_ok = False
        if not _is_string_list(sample.get("pre_text", [])):
            issues.append(
                ValidationIssue("invalid_pre_text", "pre_text must be a string array", index)
            )
            sample_ok = False
        if not _is_string_list(sample.get("post_text", [])):
            issues.append(
                ValidationIssue("invalid_post_text", "post_text must be a string array", index)
            )
            sample_ok = False
        if not _is_table(sample.get("table")):
            issues.append(
                ValidationIssue("invalid_table", "table must be a non-empty 2D string array", index)
            )
            sample_ok = False
        sample_id = sample.get("id")
        if sample_id is not None:
            key = str(sample_id)
            if key in seen_ids:
                issues.append(ValidationIssue("duplicate_id", f"Duplicate sample id: {key}", index))
                sample_ok = False
            seen_ids.add(key)
        if sample_ok:
            valid_count += 1

    return DatasetValidation(split, len(samples), valid_count, issues)


def summarize_samples(
    samples: Sequence[Mapping[str, Any]],
    *,
    split: str | None = None,
    path: str | Path | None = None,
    digest: str | None = None,
    enforce_expected_size: bool = False,
) -> SplitSummary:
    """Summarize answer types, operations, and program complexity."""

    validation = validate_samples(
        samples,
        split=split,
        enforce_expected_size=enforce_expected_size,
    )
    operations: Counter[str] = Counter()
    steps: Counter[str] = Counter()
    numeric_answers = string_answers = missing_answers = valid_programs = 0

    for sample in samples:
        qa = sample.get("qa")
        if not isinstance(qa, Mapping):
            continue
        program = qa.get("program")
        if isinstance(program, str) and program.strip():
            found = [operation.lower() for operation in _OPERATION_RE.findall(program)]
            operations.update(found)
            valid_programs += 1
            count = len(found)
            steps[str(count if count < 5 else "5+")] += 1
        answer = qa.get("exe_ans")
        if isinstance(answer, bool):
            string_answers += 1
        elif isinstance(answer, (int, float)):
            numeric_answers += 1
        elif isinstance(answer, str):
            string_answers += 1
        else:
            missing_answers += 1

    return SplitSummary(
        split=split,
        path=str(path) if path is not None else None,
        sha256=digest,
        samples=len(samples),
        valid_programs=valid_programs,
        numeric_answers=numeric_answers,
        string_answers=string_answers,
        missing_answers=missing_answers,
        operation_counts=dict(sorted(operations.items())),
        program_steps=dict(sorted(steps.items())),
        validation_ok=validation.ok,
        issue_count=len(validation.issues),
    )


def summarize_split(
    path: str | Path,
    *,
    split: str | None = None,
    enforce_expected_size: bool = False,
) -> tuple[SplitSummary, DatasetValidation]:
    """Load, validate, and summarize one JSON split."""

    source = Path(path)
    inferred_split = split or (source.stem if source.stem in EXPECTED_FINQA_SPLIT_SIZES else None)
    samples = load_split(source)
    validation = validate_samples(
        samples,
        split=inferred_split,
        enforce_expected_size=enforce_expected_size,
    )
    summary = summarize_samples(
        samples,
        split=inferred_split,
        path=source,
        digest=sha256_file(source),
        enforce_expected_size=enforce_expected_size,
    )
    return summary, validation


def summarize_data_dir(
    data_dir: str | Path,
    *,
    enforce_expected_size: bool = True,
) -> dict[str, Any]:
    """Summarize the canonical train/dev/test files in a directory."""

    root = Path(data_dir)
    split_summaries: dict[str, Any] = {}
    all_ok = True
    for split in EXPECTED_FINQA_SPLIT_SIZES:
        path = root / f"{split}.json"
        if not path.exists():
            split_summaries[split] = {
                "split": split,
                "path": str(path),
                "validation_ok": False,
                "issues": [
                    ValidationIssue("missing_split", f"Missing required split: {path}").to_dict()
                ],
            }
            all_ok = False
            continue
        summary, validation = summarize_split(
            path,
            split=split,
            enforce_expected_size=enforce_expected_size,
        )
        value = summary.to_dict()
        value["issues"] = [issue.to_dict() for issue in validation.issues]
        split_summaries[split] = value
        all_ok = all_ok and validation.ok
    return {
        "schema": "ace-finqa.data-summary.v1",
        "data_dir": str(root),
        "ok": all_ok,
        "splits": split_summaries,
    }


def iter_questions(samples: Iterable[Mapping[str, Any]]) -> Iterable[str]:
    """Yield valid questions without exposing the rest of each sample."""

    for sample in samples:
        qa = sample.get("qa")
        if isinstance(qa, Mapping) and isinstance(qa.get("question"), str):
            yield qa["question"]
