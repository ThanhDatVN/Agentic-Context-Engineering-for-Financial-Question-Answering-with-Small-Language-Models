"""Verification and provenance labels for stored experiment artifacts."""

from __future__ import annotations

import csv
import json
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from .data import summarize_data_dir


class MetricProvenance(str, Enum):
    """How a metric artifact was produced."""

    STRICT_V1 = "strict-v1"
    AUDITED_MULTI_PROFILE = "audited-multi-profile"
    THESIS_REPORTED = "thesis-reported"
    LEGACY_NOTEBOOK = "legacy-notebook"
    NOT_METRIC = "not-metric"


LEGACY_RESULT_NOTICE = (
    "Metrics stored by the original notebooks are legacy artifacts. They were not "
    "recomputed with ace-finqa's strict evaluator and must not be presented as strict-v1."
)

_METRIC_KEYS = {
    "ea",
    "pa",
    "ea_rate",
    "pa_rate",
    "ea_rate_pct",
    "pa_rate_pct",
    "ea_correct",
    "pa_correct",
    "ea_match_count",
    "pa_match_count",
    "outcome_dist",
    "execution_accuracy",
    "execution_accuracy_pct",
    "program_accuracy",
    "program_accuracy_pct",
    "execution_correct",
    "program_correct",
    "invalid_programs",
    "outcomes",
}


@dataclass(frozen=True)
class ArtifactIssue:
    """A parse, consistency, or provenance finding."""

    code: str
    message: str
    path: str | None = None
    severity: str = "error"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ArtifactInfo:
    """Metadata about one inspected artifact."""

    path: str
    kind: str
    records: int | None
    metric_provenance: MetricProvenance

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["metric_provenance"] = self.metric_provenance.value
        return value


@dataclass
class ArtifactVerification:
    """Verification result for an artifact tree or complete repository."""

    scope: str
    files_checked: int = 0
    artifacts: list[ArtifactInfo] = field(default_factory=list)
    issues: list[ArtifactIssue] = field(default_factory=list)
    data_summary: dict[str, Any] | None = None

    @property
    def ok(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)

    @property
    def legacy_metric_files(self) -> int:
        return sum(
            info.metric_provenance is MetricProvenance.LEGACY_NOTEBOOK for info in self.artifacts
        )

    def extend(self, other: ArtifactVerification) -> None:
        self.files_checked += other.files_checked
        self.artifacts.extend(other.artifacts)
        self.issues.extend(other.issues)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "ace-finqa.repository-verification.v1",
            "scope": self.scope,
            "ok": self.ok,
            "files_checked": self.files_checked,
            "legacy_metric_files": self.legacy_metric_files,
            "legacy_notice": LEGACY_RESULT_NOTICE if self.legacy_metric_files else None,
            "data_summary": self.data_summary,
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "issues": [issue.to_dict() for issue in self.issues],
        }


def _contains_metric_keys(value: Any) -> bool:
    if isinstance(value, Mapping):
        if any(str(key).lower() in _METRIC_KEYS for key in value):
            return True
        return any(_contains_metric_keys(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_metric_keys(item) for item in value[:25])
    return False


def metric_provenance(payload: Any) -> MetricProvenance:
    """Classify metrics conservatively; missing provenance is always legacy."""

    if not _contains_metric_keys(payload):
        return MetricProvenance.NOT_METRIC
    profile = payload.get("metric_profile") if isinstance(payload, Mapping) else None
    if profile is None and isinstance(payload, Mapping):
        profile = payload.get("result_profile")
    schema = payload.get("schema") if isinstance(payload, Mapping) else None
    strict_schemas = ("ace-finqa.evaluation.", "ace-finqa.results.")
    if profile == MetricProvenance.STRICT_V1.value and str(schema).startswith(strict_schemas):
        return MetricProvenance.STRICT_V1
    if (
        profile == MetricProvenance.AUDITED_MULTI_PROFILE.value
        and schema == "ace-finqa.results-audit.v2"
    ):
        return MetricProvenance.AUDITED_MULTI_PROFILE
    if (
        profile == MetricProvenance.THESIS_REPORTED.value
        and schema == "ace-finqa.thesis-results.v1"
    ):
        return MetricProvenance.THESIS_REPORTED
    return MetricProvenance.LEGACY_NOTEBOOK


def load_jsonl(path: str | Path) -> list[Any]:
    """Load JSON Lines with line-numbered errors."""

    source = Path(path)
    records: list[Any] = []
    with source.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {source}:{line_number}: {exc}") from exc
    return records


def _inspect_file(path: Path) -> tuple[ArtifactInfo | None, ArtifactIssue | None, Any]:
    try:
        if path.suffix.lower() == ".json":
            with path.open("r", encoding="utf-8") as stream:
                payload = json.load(stream)
            records = len(payload) if isinstance(payload, list) else 1
            return (
                ArtifactInfo(str(path), "json", records, metric_provenance(payload)),
                None,
                payload,
            )
        if path.suffix.lower() == ".jsonl":
            payload = load_jsonl(path)
            return (
                ArtifactInfo(str(path), "jsonl", len(payload), metric_provenance(payload)),
                None,
                payload,
            )
        if path.suffix.lower() == ".csv":
            with path.open("r", encoding="utf-8-sig", newline="") as stream:
                reader = csv.reader(stream)
                rows = list(reader)
            if rows and len(set(rows[0])) != len(rows[0]):
                return (
                    ArtifactInfo(
                        str(path),
                        "csv",
                        max(0, len(rows) - 1),
                        MetricProvenance.NOT_METRIC,
                    ),
                    ArtifactIssue(
                        "duplicate_csv_columns",
                        "CSV header contains duplicate column names",
                        str(path),
                    ),
                    rows,
                )
            return (
                ArtifactInfo(str(path), "csv", max(0, len(rows) - 1), MetricProvenance.NOT_METRIC),
                None,
                rows,
            )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, csv.Error) as exc:
        return (
            None,
            ArtifactIssue("invalid_artifact", str(exc), str(path)),
            None,
        )
    return None, None, None


def _integer_at(payload: Mapping[str, Any], *path: str) -> int | None:
    value: Any = payload
    for key in path:
        if not isinstance(value, Mapping) or key not in value:
            return None
        value = value[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return int(value)


def _compare_count(
    issues: list[ArtifactIssue],
    *,
    declared: int | None,
    observed: int,
    field: str,
    path: Path,
) -> None:
    if declared is not None and declared != observed:
        issues.append(
            ArtifactIssue(
                "artifact_count_mismatch",
                f"{field} declares {declared}, but detail records contain {observed}",
                str(path),
            )
        )


def verify_summary_details(
    summary: Mapping[str, Any],
    details: Iterable[Mapping[str, Any]],
    *,
    summary_path: str | Path = "<summary>",
) -> list[ArtifactIssue]:
    """Cross-check the known ACE summary/detail schema."""

    rows = list(details)
    source = Path(summary_path)
    issues: list[ArtifactIssue] = []
    _compare_count(
        issues,
        declared=_integer_at(summary, "total_samples"),
        observed=len(rows),
        field="total_samples",
        path=source,
    )
    ea_observed = sum(bool(row.get("ea_pass")) for row in rows)
    pa_observed = sum(bool(row.get("pa_pass")) for row in rows)
    _compare_count(
        issues,
        declared=_integer_at(summary, "test", "ea_correct"),
        observed=ea_observed,
        field="test.ea_correct",
        path=source,
    )
    _compare_count(
        issues,
        declared=_integer_at(summary, "test", "pa_correct"),
        observed=pa_observed,
        field="test.pa_correct",
        path=source,
    )
    return issues


def _load_chunk_records(paths: Iterable[Path]) -> list[Mapping[str, Any]]:
    by_position: dict[int, Mapping[str, Any]] = {}
    for path in sorted(paths):
        with path.open("r", encoding="utf-8") as stream:
            payload = json.load(stream)
        rows = payload if isinstance(payload, list) else [payload]
        for fallback, row in enumerate(rows):
            if not isinstance(row, Mapping):
                continue
            key = row.get("run_pos", row.get("idx", fallback))
            try:
                by_position[int(key)] = row
            except (TypeError, ValueError):
                continue
    return [by_position[key] for key in sorted(by_position)]


def verify_baseline_summary(
    summary: Mapping[str, Any],
    details: Iterable[Mapping[str, Any]],
    *,
    summary_path: str | Path = "<summary>",
) -> list[ArtifactIssue]:
    """Cross-check baseline summary counts against deduplicated chunk records."""

    rows = list(details)
    issues: list[ArtifactIssue] = []
    source = Path(summary_path)
    processed = [row for row in rows if not bool(row.get("skipped"))]
    comparisons = {
        "total_records": len(rows),
        "processed": len(processed),
        "ea_match_count": sum(bool(row.get("ea_match")) for row in processed),
        "pa_match_count": sum(bool(row.get("pa_match")) for row in processed),
    }
    for field_name, observed in comparisons.items():
        _compare_count(
            issues,
            declared=_integer_at(summary, field_name),
            observed=observed,
            field=field_name,
            path=source,
        )
    return issues


def verify_artifact_tree(results_dir: str | Path) -> ArtifactVerification:
    """Parse structured result files and apply known consistency checks."""

    root = Path(results_dir)
    report = ArtifactVerification(str(root))
    if not root.exists():
        report.issues.append(
            ArtifactIssue("missing_results", f"Results directory does not exist: {root}", str(root))
        )
        return report

    payloads: dict[Path, Any] = {}
    for path in sorted(root.rglob("*")):
        if path.suffix.lower() not in {".json", ".jsonl", ".csv"}:
            continue
        report.files_checked += 1
        info, issue, payload = _inspect_file(path)
        if info is not None:
            report.artifacts.append(info)
            payloads[path] = payload
        if issue is not None:
            report.issues.append(issue)

    for summary_path, summary in payloads.items():
        if summary_path.name != "test_results.json" or not isinstance(summary, Mapping):
            continue
        detail_path = summary_path.with_name("test_detail.jsonl")
        details = payloads.get(detail_path)
        if isinstance(details, list) and all(isinstance(row, Mapping) for row in details):
            report.issues.extend(
                verify_summary_details(summary, details, summary_path=summary_path)
            )

    for summary_path, summary in payloads.items():
        if summary_path.name != "summary.json" or not isinstance(summary, Mapping):
            continue
        run_root = summary_path.parent.parent
        chunks = run_root / "chunks_full_run"
        if chunks.is_dir():
            try:
                details = _load_chunk_records(chunks.glob("chunk_*.json"))
                report.issues.extend(
                    verify_baseline_summary(summary, details, summary_path=summary_path)
                )
            except (OSError, json.JSONDecodeError, ValueError) as exc:
                report.issues.append(
                    ArtifactIssue("invalid_baseline_chunks", str(exc), str(chunks))
                )

    if report.legacy_metric_files:
        report.issues.append(
            ArtifactIssue(
                "legacy_metrics_present",
                f"Found {report.legacy_metric_files} metric artifact(s). {LEGACY_RESULT_NOTICE}",
                str(root),
                severity="warning",
            )
        )
    return report


def verify_repository(
    root: str | Path,
    *,
    data_dir: str | Path | None = None,
    results_dir: str | Path | None = None,
) -> ArtifactVerification:
    """Validate canonical datasets and parse/cross-check stored artifacts.

    Explicit paths are resolved relative to ``root``. This supports repositories
    with a nonstandard artifact location while retaining the canonical
    ``data/finqa`` and ``results`` defaults.
    """

    repository = Path(root).resolve()
    report = ArtifactVerification(str(repository))
    selected_data_dir = Path(data_dir) if data_dir is not None else Path("data/finqa")
    selected_results_dir = Path(results_dir) if results_dir is not None else Path("results")
    if not selected_data_dir.is_absolute():
        selected_data_dir = repository / selected_data_dir
    if not selected_results_dir.is_absolute():
        selected_results_dir = repository / selected_results_dir
    try:
        data_summary = summarize_data_dir(selected_data_dir, enforce_expected_size=True)
        report.data_summary = data_summary
        report.files_checked += sum(
            (selected_data_dir / f"{split}.json").exists() for split in ("train", "dev", "test")
        )
        if not data_summary["ok"]:
            report.issues.append(
                ArtifactIssue(
                    "dataset_validation_failed",
                    "One or more canonical FinQA splits failed validation",
                    str(selected_data_dir),
                )
            )
    except (OSError, ValueError) as exc:
        report.issues.append(
            ArtifactIssue("dataset_validation_failed", str(exc), str(selected_data_dir))
        )

    artifact_report = verify_artifact_tree(selected_results_dir)
    report.extend(artifact_report)
    return report
