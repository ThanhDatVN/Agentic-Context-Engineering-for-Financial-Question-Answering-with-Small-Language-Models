"""Check audited metrics, provenance, thesis transcriptions, and notebooks."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

EXPECTED_PRIMARY = {
    "baseline": {
        "execution_correct": 683,
        "program_correct": 604,
        "total": 1147,
        "execution_accuracy_pct": 59.55,
        "program_accuracy_pct": 52.66,
    },
    "ace_finqa": {
        "execution_correct": 773,
        "program_correct": 710,
        "total": 1147,
        "execution_accuracy_pct": 67.39,
        "program_accuracy_pct": 61.90,
    },
    "improvement_over_baseline": {
        "additional_execution_correct": 90,
        "additional_program_correct": 106,
        "execution_accuracy_points_from_raw_counts": 7.85,
        "program_accuracy_points_from_raw_counts": 9.24,
    },
    "improvement_over_finqanet_points": {
        "execution_accuracy": 6.15,
        "program_accuracy": 3.04,
    },
}

EXPECTED_STRICT = {
    "baseline": {
        "execution_correct": 724,
        "program_correct": 642,
        "total": 1147,
        "execution_accuracy_pct": 63.12,
        "program_accuracy_pct": 55.97,
    },
    "ace_finqa": {
        "execution_correct": 777,
        "program_correct": 687,
        "total": 1147,
        "execution_accuracy_pct": 67.74,
        "program_accuracy_pct": 59.90,
    },
    "improvement_over_baseline": {
        "additional_execution_correct": 53,
        "additional_program_correct": 45,
        "execution_accuracy_points_from_raw_counts": 4.62,
        "program_accuracy_points_from_raw_counts": 3.92,
    },
}

EXPECTED_THESIS_REPORTED = {
    "baseline": {
        "execution_accuracy_pct": 59.55,
        "program_accuracy_pct": 52.66,
    },
    "ace_finqa": {
        "execution_accuracy_pct": 68.06,
        "program_accuracy_pct": 61.90,
    },
    "improvement_over_baseline_points": {
        "execution_accuracy": 8.51,
        "program_accuracy": 9.24,
    },
    "improvement_over_finqanet_points": {
        "execution_accuracy": 6.82,
        "program_accuracy": 3.04,
    },
}

EXPECTED_TABLES = {
    "table_a_1_audited_test_results.csv": [
        (
            "legacy-notebook",
            "Qwen3-8B Eng-Prompt (FS-9)",
            "test",
            "1147",
            "683",
            "604",
            "59.55",
            "52.66",
            "historical retained prediction artifact",
        ),
        (
            "legacy-notebook",
            "ACE-FinQA",
            "test",
            "1147",
            "773",
            "710",
            "67.39",
            "61.90",
            "historical retained prediction artifact",
        ),
        (
            "strict-v1",
            "Qwen3-8B Eng-Prompt (FS-9)",
            "test",
            "1147",
            "724",
            "642",
            "63.12",
            "55.97",
            "recomputed from historical predictions",
        ),
        (
            "strict-v1",
            "ACE-FinQA",
            "test",
            "1147",
            "777",
            "687",
            "67.74",
            "59.90",
            "recomputed from historical predictions",
        ),
    ],
    "table_4_1_qwen3_baseline_by_steps.csv": [
        ("1", "654", "59.79", "56.27", "3.52", "Reference bucket"),
        ("2", "409", "63.08", "54.28", "8.80", "Unusually high EA; wide gap"),
        ("3", "55", "52.73", "18.18", "34.55", "PA collapse; many lucky guesses"),
        ("4", "10", "30.00", "30.00", "0.00", "Cliff drop; small sample and wide CI"),
        ("5+", "19", "10.53", "5.26", "5.27", "Nearly unsolved"),
    ],
    "table_4_2_qwen3_baseline_by_operator.csv": [
        ("greater", "20", "90.00", "Strong binary comparison; small sample"),
        ("table_average", "15", "80.00", "Clear pattern; small sample"),
        ("divide", "399", "61.65", "Common operation; above average"),
        ("add", "163", "59.51", "Near the baseline average"),
        ("multiply", "66", "59.09", "Similar to addition"),
        ("subtract", "457", "58.86", "Most common; operand order is a typical error"),
        ("table_sum", "10", "20.00", "Row-name lookup is difficult; small sample"),
        ("table_max", "10", "0.00", "No correct examples; very small sample"),
        ("table_min", "4", "0.00", "No correct examples; very small sample"),
        ("exp", "3", "0.00", "No correct examples; very small sample"),
    ],
    "table_4_3_qwen3_baseline_error_classes.csv": [
        ("missing_steps", "Omits one or more required operations, especially in 3+-step programs."),
        ("extra_steps", "Adds unnecessary operations to a problem that needs a shorter program."),
        (
            "wrong_number",
            "Uses the correct reasoning structure but extracts the wrong year, row, or value.",
        ),
        ("no_program", "Produces no valid FinQA DSL program."),
        (
            "sign/order_error",
            "Reverses subtraction operands or temporal order, producing the wrong sign.",
        ),
    ],
    "table_4_4_model_comparison.csv": [
        ("Qwen3-8B Eng-Prompt (FS-9)", "59.55", "52.66", "", ""),
        ("FinQANet (RoBERTa-large)", "61.24", "58.86", "", ""),
        ("ACE-FinQA", "68.06", "61.90", "6.82", "3.04"),
        ("FinQANet-Gold (oracle retriever)", "70.00", "68.76", "", ""),
        ("Human Expert (CPA/MBA)", "91.16", "87.49", "", ""),
    ],
    "table_4_5_ace_gain_over_qwen3_by_steps.csv": [
        ("1", "522", "65.97", "70.69", "4.72", "Good"),
        ("2", "289", "64.81", "70.93", "6.12", "Good"),
        ("3", "43", "32.56", "48.84", "16.28", "Cliff reduced"),
        ("4", "14", "21.43", "35.71", "14.28", "Wide CI"),
        ("5+", "15", "20.00", "33.33", "13.33", "Wide CI"),
    ],
    "table_4_6_qwen3_ace_outcomes.csv": [
        ("correct", "459", "51.98", "547", "61.95"),
        ("lucky_guess", "92", "10.42", "54", "6.11"),
        ("execution_mismatch", "12", "1.36", "8", "0.91"),
        ("wrong_reasoning", "264", "29.90", "197", "22.31"),
        ("no_program", "56", "6.34", "77", "8.72"),
    ],
    "table_4_7_ablation.csv": [
        ("Full ACE-FinQA", "68.06", "61.90", "", ""),
        ("A1: no cluster pipeline", "64.80", "58.10", "-3.3", "-3.8"),
        ("A2: no Verify-Iterate", "65.00", "56.70", "-3.1", "-5.2"),
        ("A3: flat memory, no Tier 1/2", "66.30", "60.00", "-1.8", "-1.9"),
        (
            "A4: heuristic/harm instead of dev-EMA",
            "65.80",
            "57.50",
            "-2.3",
            "-4.4",
        ),
        ("A5: two-layer Quality Gate", "64.30", "56.10", "-3.8", "-5.8"),
        ("A6: no role-based retrieval", "66.50", "59.70", "-1.6", "-2.2"),
        ("A7: EA-only selection, no PA guard", "68.30", "55.70", "0.2", "-6.2"),
    ],
}

EXPECTED_CURRENT_RERUN_CONFIG = {
    "random_seed": 42,
    "generator_temperature": 0.0,
    "generator_quantization": "4-bit NF4",
    "context_length_tokens": 4096,
    "few_shot_examples": 9,
    "evaluator": "FinQA round-to-5-decimals",
    "reflector": "GPT-4o mini",
    "reflector_temperature": 0.0,
    "reflector_response_format": "JSON",
    "verify_iterate_rounds": 3,
    "verify_require_pa": True,
    "training_examples_target": 600,
    "training_epochs": 1,
    "dev_lift_examples": 100,
    "initial_playbook": "empty",
    "warm_start": False,
    "manual_playbook_editing": False,
    "composite_ea_weight": 0.6,
    "composite_pa_weight": 0.4,
    "pa_guard_tolerance": 0.02,
}

EXPECTED_HISTORICAL_CONFIG = {
    "completed_epochs": 2,
    "train_subset_size": 594,
    "completed_steps": 780,
    "reflector": "gpt-4o",
    "max_verify_rounds": 5,
    "verify_require_pa": False,
    "generator_precision": "BF16 (historical notebook execution output)",
    "context_length_tokens": 8192,
}

METHOD_ORDER = (
    "Qwen3-8B",
    "FinQANet (RoBERTa-large)",
    "ACE-FinQA",
    "FinQANet-Gold",
    "Human Expert",
)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _expect(issues: list[str], label: str, actual: Any, expected: Any) -> None:
    if actual != expected:
        issues.append(f"{label}: expected {expected!r}, found {actual!r}")


def _read_csv_rows(path: Path) -> list[tuple[str, ...]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.reader(stream))
    if not rows:
        return []
    return [tuple(row) for row in rows[1:]]


def _check_manifest(root: Path, issues: list[str]) -> None:
    manifest = _load_json(root / "results" / "manifest.json")
    _expect(issues, "manifest schema", manifest.get("schema"), "ace-finqa.results-audit.v2")
    _expect(issues, "manifest schema version", manifest.get("schema_version"), 2)
    _expect(issues, "result profile", manifest.get("result_profile"), "audited-multi-profile")
    _expect(issues, "audit status", manifest.get("audit_status"), "thesis-errata-required")
    _expect(issues, "test records", manifest.get("task", {}).get("records"), 1147)

    for section, expected_groups in (
        ("primary_result", EXPECTED_PRIMARY),
        ("strict_v1_recomputation", EXPECTED_STRICT),
        ("thesis_reported", EXPECTED_THESIS_REPORTED),
    ):
        observed_section = manifest.get(section, {})
        for group, expected in expected_groups.items():
            observed = observed_section.get(group, {})
            for field, value in expected.items():
                _expect(issues, f"{section}.{group}.{field}", observed.get(field), value)

    for section in ("primary_result", "strict_v1_recomputation"):
        observed = manifest.get(section, {})
        baseline = observed.get("baseline", {})
        ace = observed.get("ace_finqa", {})
        for label, result in (("baseline", baseline), ("ace_finqa", ace)):
            total = result.get("total")
            if isinstance(total, int) and total:
                for count_field, rate_field in (
                    ("execution_correct", "execution_accuracy_pct"),
                    ("program_correct", "program_accuracy_pct"),
                ):
                    count = result.get(count_field)
                    if isinstance(count, int):
                        _expect(
                            issues,
                            f"{section}.{label}.{rate_field} arithmetic",
                            result.get(rate_field),
                            round(100 * count / total, 2),
                        )
        if all(
            isinstance(value, int)
            for value in (
                baseline.get("total"),
                baseline.get("execution_correct"),
                baseline.get("program_correct"),
                ace.get("execution_correct"),
                ace.get("program_correct"),
            )
        ):
            total = baseline["total"]
            improvement = observed.get("improvement_over_baseline", {})
            _expect(
                issues,
                f"{section} EA gain arithmetic",
                improvement.get("execution_accuracy_points_from_raw_counts"),
                round(100 * (ace["execution_correct"] - baseline["execution_correct"]) / total, 2),
            )
            _expect(
                issues,
                f"{section} PA gain arithmetic",
                improvement.get("program_accuracy_points_from_raw_counts"),
                round(100 * (ace["program_correct"] - baseline["program_correct"]) / total, 2),
            )

    thesis = manifest.get("thesis_reported", {})
    _expect(issues, "source document", thesis.get("source", {}).get("document"), "docs/thesis.pdf")
    _expect(issues, "primary table", thesis.get("source", {}).get("primary_table"), "4.4")
    _expect(issues, "thesis result status", thesis.get("status"), "transcribed-not-verified")

    for section, expected_config in (
        ("observed_historical_run_configuration", EXPECTED_HISTORICAL_CONFIG),
        ("current_rerun_profile", EXPECTED_CURRENT_RERUN_CONFIG),
    ):
        config = manifest.get(section, {})
        for field, expected in expected_config.items():
            _expect(issues, f"{section}.{field}", config.get(field), expected)

    evidence = manifest.get("historical_evidence", {})
    _expect(
        issues,
        "historical evidence commit",
        evidence.get("git_commit"),
        "084446bce6b7b02ff29dc1db6df2f6d32a062974",
    )
    evidence_files = evidence.get("files", {})
    _expect(issues, "historical evidence file count", len(evidence_files), 6)
    for label, details in evidence_files.items():
        if len(str(details.get("git_blob_sha1", ""))) != 40:
            issues.append(f"historical evidence {label}: invalid Git blob SHA-1")
        if len(str(details.get("sha256", ""))) != 64:
            issues.append(f"historical evidence {label}: invalid SHA-256")

    known_ids = {item.get("id") for item in manifest.get("known_inconsistencies", [])}
    _expect(
        issues,
        "known inconsistency IDs",
        known_ids,
        {
            "thesis-test-ea",
            "thesis-outcome-split",
            "thesis-complexity-aggregate",
            "reported-versus-observed-configuration",
        },
    )

    for table_id, relative in manifest.get("tables", {}).items():
        if not (root / "results" / relative).is_file():
            issues.append(f"manifest table {table_id}: missing {relative}")
    for figure_id, relative in manifest.get("figures", {}).items():
        if not (root / "results" / relative).is_file():
            issues.append(f"manifest figure {figure_id}: missing {relative}")


def _check_tables(root: Path, issues: list[str]) -> None:
    table_dir = root / "results" / "tables"
    for name, expected in EXPECTED_TABLES.items():
        path = table_dir / name
        if not path.is_file():
            issues.append(f"missing thesis table: {path.relative_to(root)}")
            continue
        _expect(issues, name, _read_csv_rows(path), expected)


def _check_notebooks(root: Path, issues: list[str]) -> None:
    expected_fragments = {
        "01_qwen3_baseline.ipynb": (
            '"metric_profile": "notebook-diagnostic"',
            'model_name             = "unsloth/Qwen3-8B-bnb-4bit"',
            "RANDOM_SEED = 42",
            "max_seq_length         = 4096",
            "load_in_4bit           = True",
            "def check_ea(predicted, gold, decimal_places=5)",
            "_STRICT_TABLE_FIXTURE",
        ),
        "02_ace_finqa.ipynb": (
            'MODEL_NAME = "unsloth/Qwen3-8B-bnb-4bit"',
            "RANDOM_SEED = 42",
            "MAX_SEQ_LENGTH = 4096",
            "load_in_4bit           = True",
            "EA_DECIMAL_PLACES     = 5",
            "def check_ea(predicted, gold, decimal_places=5)",
            "_STRICT_TABLE_FIXTURE",
            'HYBRID_MODEL_REFLECTOR  = "gpt-4o-mini"',
            "TRAIN_SUBSET     = 600",
            "NUM_EPOCHS            = 1",
            "Fill a short quota",
            "MAX_VERIFY_ROUNDS = 3",
            'ACE_FINQA_VERIFY_REQUIRE_PA", "1"',
            'response_format={"type": "json_object"}',
            "passed = ea and pa",
            "'metric_profile': 'notebook-diagnostic'",
        ),
    }
    forbidden_fragments = {
        "01_qwen3_baseline.ipynb": (
            "historical experiment",
            "df = pd.DataFrame()",
            "tol=0.01",
            "replace('%','')",
            "thesis_baseline",
        ),
        "02_ace_finqa.ipynb": (
            "historical experiment",
            'ACE_FINQA_VERIFY_REQUIRE_PA", "0"',
            "retry_temp",
            "last_round_relaxed",
            "Final-round similarity fallback",
            "load_in_4bit           = False",
            "NUM_EPOCHS            = 2",
            "USE_BARE_PROMPT",
            "EA_TOLERANCE",
            "df = pd.DataFrame()",
            "tol=0.01",
            "replace('%','')",
            "ACE_thesis",
        ),
    }
    for name, fragments in expected_fragments.items():
        notebook = _load_json(root / "notebooks" / name)
        _expect(
            issues,
            f"{name} structure version",
            notebook.get("metadata", {}).get("ace_finqa_structure_version"),
            2,
        )
        source = "\n".join("".join(cell.get("source", [])) for cell in notebook["cells"])
        for fragment in fragments:
            if fragment not in source:
                issues.append(f"{name}: missing canonical fragment {fragment!r}")
        for fragment in forbidden_fragments[name]:
            if fragment in source:
                issues.append(f"{name}: contains conflicting fragment {fragment!r}")

        prompt_examples = source.count("\nQ:")
        if prompt_examples != 9:
            issues.append(f"{name}: expected exactly nine FS-9 prompt examples")


def _check_public_documents(root: Path, issues: list[str]) -> None:
    expected_fragments = {
        "README.md": (
            "67.39%",
            "7.85 EA points",
            "68.06%",
            "61.90%",
            "results/audit.md",
        ),
        "docs/results.md": (
            "67.39%",
            "## Audited historical test result",
            "68.06%",
            "61.90%",
            "## Thesis-reported ablation study",
            "../results/figures/ablation_effects.svg",
        ),
        "results/report.md": (
            "67.39% EA / 61.90% PA",
            "## Audited test comparison",
            "## Thesis-reported comparison",
            "figures/complexity_gain.svg",
        ),
        "results/README.md": (
            "67.39% execution accuracy",
            "61.90% program accuracy",
            "not raw-artifact verified",
        ),
        "results/audit.md": (
            "773/1,147",
            "710/1,147",
            "68.06% EA / 62.85% PA",
            "084446bce6b7b02ff29dc1db6df2f6d32a062974",
        ),
    }
    for relative, fragments in expected_fragments.items():
        text = (root / relative).read_text(encoding="utf-8")
        for fragment in fragments:
            if fragment not in text:
                issues.append(f"{relative}: missing audited disclosure {fragment!r}")
        if relative in {"docs/results.md", "results/report.md"}:
            table_start = text.find("FinQANet (RoBERTa-large)")
            table_start = text.rfind("Qwen3-8B", 0, table_start) if table_start >= 0 else -1
            comparison = text[table_start:] if table_start >= 0 else ""
            positions = [comparison.find(method) for method in METHOD_ORDER]
            if any(position < 0 for position in positions) or positions != sorted(positions):
                issues.append(f"{relative}: model comparison is missing or out of thesis order")


def check_repository(root: Path) -> list[str]:
    issues: list[str] = []
    _check_manifest(root, issues)
    _check_tables(root, issues)
    _check_notebooks(root, issues)
    _check_public_documents(root, issues)
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    issues = check_repository(args.root.resolve())
    if issues:
        print("Repository consistency check failed:")
        for issue in issues:
            print(f"  - {issue}")
        return 1
    print("Audited metrics, provenance, thesis transcriptions, and notebooks are consistent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
