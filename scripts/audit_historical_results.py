"""Recompute the result audit from retained files in Git history."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import shutil

# Git is invoked without a shell to read validated, immutable local object names.
import subprocess  # nosec B404
from pathlib import Path
from typing import Any

from ace_finqa.data import load_split, sha256_file
from ace_finqa.evaluation import evaluate_predictions


def _git_object(root: Path, commit: str, path: str) -> bytes:
    git_executable = shutil.which("git")
    if git_executable is None:
        raise RuntimeError("Git is required to inspect the retained historical objects")
    relative = Path(path)
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise RuntimeError(f"Invalid historical commit ID: {commit!r}")
    if relative.is_absolute() or ".." in relative.parts:
        raise RuntimeError(f"Invalid historical object path: {path!r}")
    process = subprocess.run(
        [git_executable, "cat-file", "blob", f"{commit}:{path}"],
        cwd=root,
        check=False,
        capture_output=True,
    )  # nosec B603
    if process.returncode:
        detail = process.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(
            f"Could not read {commit}:{path}. Fetch full Git history and retry. {detail}"
        )
    return process.stdout


def _expect(label: str, actual: Any, expected: Any) -> None:
    if actual != expected:
        raise RuntimeError(f"{label}: expected {expected!r}, found {actual!r}")


def _rates(*, total: int, execution_correct: int, program_correct: int) -> dict[str, Any]:
    return {
        "execution_correct": execution_correct,
        "program_correct": program_correct,
        "total": total,
        "execution_accuracy_pct": round(100 * execution_correct / total, 2),
        "program_accuracy_pct": round(100 * program_correct / total, 2),
    }


def _check_result(label: str, observed: dict[str, Any], expected: dict[str, Any]) -> None:
    for field, value in observed.items():
        _expect(f"{label}.{field}", value, expected.get(field))


def audit(root: Path) -> dict[str, Any]:
    manifest = json.loads((root / "results" / "manifest.json").read_text(encoding="utf-8"))
    evidence = manifest["historical_evidence"]
    commit = evidence["git_commit"]
    blobs: dict[str, bytes] = {}
    for label, details in evidence["files"].items():
        blob = _git_object(root, commit, details["path_at_commit"])
        _expect(
            f"{label} SHA-256",
            hashlib.sha256(blob).hexdigest(),
            details["sha256"],
        )
        blobs[label] = blob

    data_path = root / "data" / "finqa" / "test.json"
    _expect("test data SHA-256", sha256_file(data_path), evidence["dataset_sha256"])
    samples = load_split(data_path)

    baseline_rows = list(csv.DictReader(io.StringIO(blobs["baseline_records"].decode("utf-8"))))
    ace_rows = [
        json.loads(line)
        for line in blobs["ace_records"].decode("utf-8").splitlines()
        if line.strip()
    ]
    total = len(samples)
    _expect("baseline prediction count", len(baseline_rows), total)
    _expect("ACE prediction count", len(ace_rows), total)

    legacy_baseline = _rates(
        total=total,
        execution_correct=sum(row["ea_match"] == "True" for row in baseline_rows),
        program_correct=sum(row["pa_match"] == "True" for row in baseline_rows),
    )
    legacy_ace = _rates(
        total=total,
        execution_correct=sum(bool(row["ea_pass"]) for row in ace_rows),
        program_correct=sum(bool(row["pa_pass"]) for row in ace_rows),
    )
    _check_result(
        "primary_result.baseline", legacy_baseline, manifest["primary_result"]["baseline"]
    )
    _check_result("primary_result.ace_finqa", legacy_ace, manifest["primary_result"]["ace_finqa"])

    strict_baseline_report = evaluate_predictions(samples, baseline_rows)
    strict_ace_report = evaluate_predictions(samples, ace_rows)
    strict_baseline = _rates(
        total=total,
        execution_correct=strict_baseline_report.counts["execution_correct"],
        program_correct=strict_baseline_report.counts["program_correct"],
    )
    strict_ace = _rates(
        total=total,
        execution_correct=strict_ace_report.counts["execution_correct"],
        program_correct=strict_ace_report.counts["program_correct"],
    )
    strict_expected = manifest["strict_v1_recomputation"]
    _check_result("strict_v1_recomputation.baseline", strict_baseline, strict_expected["baseline"])
    _check_result("strict_v1_recomputation.ace_finqa", strict_ace, strict_expected["ace_finqa"])

    run_meta = json.loads(blobs["ace_run_metadata"].decode("utf-8"))
    observed_config = {
        "completed_epochs": run_meta["completed_epochs"],
        "train_subset_size": run_meta["train_subset_size"],
        "completed_steps": run_meta["total_steps"],
        "reflector": run_meta["r20_flags"]["reflector_model"],
        "max_verify_rounds": run_meta["r20_flags"]["max_verify_rounds"],
        "verify_require_pa": run_meta["r20_flags"]["verify_require_pa"],
        "context_length_tokens": run_meta["hyperparams"]["max_seq_length"],
    }
    expected_config = manifest["observed_historical_run_configuration"]
    for field, value in observed_config.items():
        _expect(f"observed_historical_run_configuration.{field}", value, expected_config[field])

    notebook_text = blobs["historical_ace_notebook"].decode("utf-8")
    for fragment in (
        "load_in_4bit           = False",
        "dtype=torch.bfloat16",
        "quantization=None",
    ):
        if fragment not in notebook_text:
            raise RuntimeError(f"Historical ACE notebook is missing runtime evidence {fragment!r}")

    return {
        "schema": "ace-finqa.historical-audit.v1",
        "source_commit": commit,
        "dataset_records": total,
        "legacy_notebook": {"baseline": legacy_baseline, "ace_finqa": legacy_ace},
        "strict_v1": {"baseline": strict_baseline, "ace_finqa": strict_ace},
        "observed_historical_run_configuration": observed_config,
        "ok": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    try:
        result = audit(args.root.resolve())
    except (KeyError, OSError, UnicodeError, ValueError, RuntimeError) as exc:
        print(f"Historical result audit failed: {exc}")
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
