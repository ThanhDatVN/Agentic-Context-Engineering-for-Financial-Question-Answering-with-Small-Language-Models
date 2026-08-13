"""Strict, reproducible evaluation for FinQA program predictions.

This module deliberately ignores notebook-era ``ea_match``/``pa_match`` flags
and recomputes every outcome with the dependency-free strict DSL evaluator.
Historical result files are handled separately by :mod:`ace_finqa.artifacts`
and are always labelled ``legacy-notebook``.
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .data import DatasetError, load_split, sha256_file, validate_samples
from .dsl import (
    DSLParseError,
    canonicalize_program_strict,
    execute_program,
    extract_program,
    parse_program,
)
from .metrics import MetricAccumulator, MetricProfile, answers_equal_strict

EVALUATION_SCHEMA = "ace-finqa.evaluation.v1"
STRICT_METRIC_NOTICE = (
    "Metrics were recomputed with ace-finqa strict-v1. Stored notebook flags "
    "were ignored; strict-v1 is a repository metric profile, not a claim of "
    "bit-for-bit equivalence with the upstream FinQA evaluator."
)


class EvaluationError(ValueError):
    """Raised when evaluation inputs are incomplete, ambiguous, or malformed."""


@dataclass(frozen=True)
class Prediction:
    """One prediction aligned to a dataset index."""

    index: int
    program: str | None
    raw_output: Any = None
    extracted: bool = False


@dataclass(frozen=True)
class EvaluationRecord:
    """Auditable result for one question."""

    index: int
    sample_id: str | None
    question: str
    gold_program: str | None
    predicted_program: str | None
    gold_canonical: str | None
    predicted_canonical: str | None
    gold_answer: Any
    predicted_answer: Any
    execution_accuracy: bool
    program_accuracy: bool
    program_valid: bool
    program_extracted: bool
    outcome: str
    complexity: str
    error: Mapping[str, Any] | None = None
    gold_program_valid: bool = True
    gold_execution_matches_answer: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EvaluationReport:
    """Strict evaluation report with explicit coverage and provenance."""

    dataset_records: int
    predictions_received: int
    counts: Mapping[str, Any]
    coverage: float
    by_complexity: Mapping[str, Mapping[str, Any]]
    dataset_path: str | None = None
    dataset_sha256: str | None = None
    predictions_path: str | None = None
    predictions_sha256: str | None = None
    warnings: list[str] = field(default_factory=list)
    details: list[EvaluationRecord] = field(default_factory=list)

    def to_dict(self, *, include_details: bool = False) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema": EVALUATION_SCHEMA,
            "metric_profile": MetricProfile.STRICT_V1.value,
            "metric_notice": STRICT_METRIC_NOTICE,
            "dataset": {
                "path": self.dataset_path,
                "sha256": self.dataset_sha256,
                "records": self.dataset_records,
            },
            "predictions": {
                "path": self.predictions_path,
                "sha256": self.predictions_sha256,
                "records": self.predictions_received,
                "coverage": round(self.coverage, 6),
            },
            "counts": dict(self.counts),
            "by_complexity": {
                key: dict(value) for key, value in sorted(self.by_complexity.items())
            },
            "warnings": list(self.warnings),
        }
        if include_details:
            payload["details"] = [record.to_dict() for record in self.details]
        return payload


_INDEX_KEYS = ("idx", "index", "source_idx", "global_idx", "run_pos")
_PROGRAM_KEYS = ("pred_prog", "predicted_program", "program")
_RAW_KEYS = ("pred_text", "prediction", "output", "response", "text")


def _coerce_index(value: Any, *, position: int) -> int:
    if isinstance(value, bool):
        raise EvaluationError(f"Prediction {position} has a boolean index")
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    raise EvaluationError(f"Prediction {position} has an invalid index: {value!r}")


def _mapping_index(record: Mapping[str, Any], *, position: int) -> int:
    for key in _INDEX_KEYS:
        if key in record and record[key] is not None:
            return _coerce_index(record[key], position=position)
    return position


def _first_nonempty(record: Mapping[str, Any], keys: Sequence[str]) -> Any:
    for key in keys:
        value = record.get(key)
        if value is not None and (not isinstance(value, str) or value.strip()):
            return value
    return None


def normalize_predictions(
    records: Sequence[Any],
    *,
    dataset_size: int,
    require_complete: bool = True,
) -> list[Prediction]:
    """Normalize common JSON/JSONL/CSV outputs without trusting stored scores.

    Records without an explicit index are aligned by list position. An explicit
    but malformed index, duplicate index, or out-of-range index is an error.
    ``require_complete`` defaults to true to prevent partial runs being reported
    with an ambiguous denominator.
    """

    predictions: list[Prediction] = []
    seen: set[int] = set()
    for position, record in enumerate(records):
        if isinstance(record, Mapping):
            index = _mapping_index(record, position=position)
            direct = _first_nonempty(record, _PROGRAM_KEYS)
            raw = _first_nonempty(record, _RAW_KEYS)
            if direct is not None and not isinstance(direct, str):
                raise EvaluationError(
                    f"Prediction {position} program must be text, got {type(direct).__name__}"
                )
            program = direct.strip() if isinstance(direct, str) else None
            extracted = False
            if program is None and raw is not None:
                program = extract_program(raw)
                extracted = program is not None
        elif isinstance(record, str):
            index = position
            raw = record
            program = extract_program(record)
            extracted = program is not None
        elif record is None:
            index = position
            raw = None
            program = None
            extracted = False
        else:
            raise EvaluationError(f"Prediction {position} must be an object, string, or null")

        if index < 0 or index >= dataset_size:
            raise EvaluationError(
                f"Prediction {position} index {index} is outside [0, {dataset_size})"
            )
        if index in seen:
            raise EvaluationError(f"Duplicate prediction index: {index}")
        seen.add(index)
        predictions.append(Prediction(index, program, raw, extracted))

    if require_complete:
        missing = sorted(set(range(dataset_size)) - seen)
        if missing:
            preview = ", ".join(map(str, missing[:10]))
            suffix = " ..." if len(missing) > 10 else ""
            raise EvaluationError(
                f"Predictions cover {len(seen)}/{dataset_size} records; "
                f"missing indices: {preview}{suffix}. Use allow-partial explicitly "
                "when a subset denominator is intended."
            )
    return sorted(predictions, key=lambda item: item.index)


def _unwrap_prediction_payload(payload: Any) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, Mapping):
        for key in ("predictions", "records", "results", "details"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
    raise EvaluationError(
        "Prediction payload must be an array or contain an array named "
        "predictions, records, results, or details"
    )


def load_predictions(path: str | Path) -> list[Any]:
    """Load prediction records from JSON, JSONL, or CSV."""

    source = Path(path)
    suffix = source.suffix.casefold()
    try:
        if suffix == ".json":
            with source.open("r", encoding="utf-8") as stream:
                return _unwrap_prediction_payload(json.load(stream))
        if suffix == ".jsonl":
            records: list[Any] = []
            with source.open("r", encoding="utf-8") as stream:
                for line_number, line in enumerate(stream, 1):
                    if not line.strip():
                        continue
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError as exc:
                        raise EvaluationError(
                            f"Invalid JSONL at {source}:{line_number}: {exc}"
                        ) from exc
            return records
        if suffix == ".csv":
            with source.open("r", encoding="utf-8-sig", newline="") as stream:
                return list(csv.DictReader(stream))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise EvaluationError(f"Could not load predictions {source}: {exc}") from exc
    raise EvaluationError(f"Unsupported prediction format: {source.suffix or '<none>'}")


def _complexity(program: Any) -> str:
    if not isinstance(program, str) or not program.strip():
        return "invalid"
    try:
        steps = len(parse_program(program))
    except DSLParseError:
        return "invalid"
    return str(steps) if steps < 5 else "5+"


def _safe_canonical(program: Any) -> tuple[str | None, Mapping[str, Any] | None]:
    if not isinstance(program, str) or not program.strip():
        return None, {
            "stage": "extraction",
            "code": "NO_PROGRAM",
            "message": "No FinQA program was provided or extracted.",
        }
    try:
        return canonicalize_program_strict(program), None
    except DSLParseError as exc:
        return None, asdict(exc.detail)


def evaluate_predictions(
    samples: Sequence[Mapping[str, Any]],
    prediction_records: Sequence[Any],
    *,
    require_complete: bool = True,
    dataset_path: str | None = None,
    dataset_sha256: str | None = None,
    predictions_path: str | None = None,
    predictions_sha256: str | None = None,
) -> EvaluationReport:
    """Recompute strict EA, PA, validity, and outcome quadrants."""

    validation = validate_samples(samples)
    if not validation.ok:
        first = validation.issues[0]
        raise EvaluationError(
            f"Dataset validation failed at index {first.index}: {first.code}: {first.message}"
        )

    predictions = normalize_predictions(
        prediction_records,
        dataset_size=len(samples),
        require_complete=require_complete,
    )
    overall = MetricAccumulator()
    complexity_accumulators: dict[str, MetricAccumulator] = {}
    details: list[EvaluationRecord] = []
    warning_counts: Counter[str] = Counter()

    for prediction in predictions:
        sample = samples[prediction.index]
        qa = sample["qa"]
        gold_program = qa.get("program")
        gold_answer = qa.get("exe_ans")
        table = sample.get("table")
        question = str(qa.get("question", ""))

        predicted_canonical, prediction_error = _safe_canonical(prediction.program)
        predicted_execution = execute_program(prediction.program or "", table)
        program_valid = predicted_canonical is not None and predicted_execution.ok
        predicted_answer = predicted_execution.value if predicted_execution.ok else None
        if prediction_error is None and predicted_execution.error is not None:
            prediction_error = asdict(predicted_execution.error)

        gold_canonical, _gold_error = _safe_canonical(gold_program)
        gold_valid = gold_canonical is not None
        gold_execution_match: bool | None = None
        if isinstance(gold_program, str) and gold_program.strip():
            gold_execution = execute_program(gold_program, table)
            gold_valid = gold_valid and gold_execution.ok
            if gold_execution.ok:
                gold_execution_match = answers_equal_strict(gold_execution.value, gold_answer)
                if not gold_execution_match:
                    warning_counts["gold_execution_mismatch"] += 1
            if not gold_valid:
                warning_counts["invalid_gold_program"] += 1
        else:
            warning_counts["invalid_gold_program"] += 1

        ea = program_valid and answers_equal_strict(predicted_answer, gold_answer)
        pa = program_valid and gold_valid and predicted_canonical == gold_canonical
        outcome = overall.add(ea=ea, pa=pa, program_valid=program_valid)
        complexity = _complexity(gold_program)
        bucket = complexity_accumulators.setdefault(complexity, MetricAccumulator())
        bucket.add(ea=ea, pa=pa, program_valid=program_valid)

        sample_id = sample.get("id")
        details.append(
            EvaluationRecord(
                index=prediction.index,
                sample_id=str(sample_id) if sample_id is not None else None,
                question=question,
                gold_program=gold_program if isinstance(gold_program, str) else None,
                predicted_program=prediction.program,
                gold_canonical=gold_canonical,
                predicted_canonical=predicted_canonical,
                gold_answer=gold_answer,
                predicted_answer=predicted_answer,
                execution_accuracy=ea,
                program_accuracy=pa,
                program_valid=program_valid,
                program_extracted=prediction.extracted,
                outcome=outcome.value,
                complexity=complexity,
                error=prediction_error,
                gold_program_valid=gold_valid,
                gold_execution_matches_answer=gold_execution_match,
            )
        )

    warnings: list[str] = []
    if len(predictions) != len(samples):
        warnings.append(f"Partial evaluation: {len(predictions)}/{len(samples)} dataset records.")
    if warning_counts["invalid_gold_program"]:
        warnings.append(
            f"{warning_counts['invalid_gold_program']} gold programs failed strict "
            "validation/execution."
        )
    if warning_counts["gold_execution_mismatch"]:
        warnings.append(
            f"{warning_counts['gold_execution_mismatch']} executable gold programs did not "
            "match qa.exe_ans under strict-v1."
        )

    return EvaluationReport(
        dataset_records=len(samples),
        predictions_received=len(predictions),
        counts=overall.snapshot().to_dict(),
        coverage=len(predictions) / len(samples) if samples else 0.0,
        by_complexity={
            key: accumulator.snapshot().to_dict()
            for key, accumulator in complexity_accumulators.items()
        },
        dataset_path=dataset_path,
        dataset_sha256=dataset_sha256,
        predictions_path=predictions_path,
        predictions_sha256=predictions_sha256,
        warnings=warnings,
        details=details,
    )


def evaluate_files(
    dataset_path: str | Path,
    predictions_path: str | Path,
    *,
    require_complete: bool = True,
) -> EvaluationReport:
    """Load two files, evaluate them, and record their exact content hashes."""

    dataset_source = Path(dataset_path)
    predictions_source = Path(predictions_path)
    try:
        samples = load_split(dataset_source)
    except DatasetError as exc:
        raise EvaluationError(str(exc)) from exc
    records = load_predictions(predictions_source)
    return evaluate_predictions(
        samples,
        records,
        require_complete=require_complete,
        dataset_path=dataset_source.as_posix(),
        dataset_sha256=sha256_file(dataset_source),
        predictions_path=predictions_source.as_posix(),
        predictions_sha256=sha256_file(predictions_source),
    )
