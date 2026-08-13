from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from ace_finqa.artifacts import (
    MetricProvenance,
    metric_provenance,
    verify_artifact_tree,
    verify_baseline_summary,
    verify_summary_details,
)


class ArtifactTests(unittest.TestCase):
    def test_strict_evaluation_v1_count_names_are_recognized(self) -> None:
        payload = {
            "schema": "ace-finqa.evaluation.v1",
            "metric_profile": "strict-v1",
            "counts": {
                "execution_correct": 1,
                "program_correct": 1,
                "execution_accuracy": 1.0,
                "program_accuracy": 1.0,
            },
        }
        self.assertIs(metric_provenance(payload), MetricProvenance.STRICT_V1)

    def test_strict_result_manifest_is_recognized(self) -> None:
        payload = {
            "schema": "ace-finqa.results.v1",
            "metric_profile": "strict-v1",
            "ace": {"execution_accuracy": 0.67, "program_accuracy": 0.59},
        }
        self.assertIs(metric_provenance(payload), MetricProvenance.STRICT_V1)

    def test_audited_multi_profile_manifest_is_recognized(self) -> None:
        payload = {
            "schema": "ace-finqa.results-audit.v2",
            "result_profile": "audited-multi-profile",
            "primary_result": {
                "ace_finqa": {
                    "execution_accuracy_pct": 67.39,
                    "program_accuracy_pct": 61.90,
                }
            },
        }
        self.assertIs(
            metric_provenance(payload),
            MetricProvenance.AUDITED_MULTI_PROFILE,
        )

    def test_thesis_result_manifest_is_recognized(self) -> None:
        payload = {
            "schema": "ace-finqa.thesis-results.v1",
            "result_profile": "thesis-reported",
            "headline": {"ace_finqa": {"execution_accuracy": 68.06}},
        }
        self.assertIs(metric_provenance(payload), MetricProvenance.THESIS_REPORTED)

    def test_unlabeled_metric_payload_is_legacy(self) -> None:
        self.assertIs(
            metric_provenance({"test": {"EA": 0.7, "PA": 0.6}}),
            MetricProvenance.LEGACY_NOTEBOOK,
        )

    def test_strict_payload_requires_profile_and_schema(self) -> None:
        payload = {
            "schema": "ace-finqa.evaluation.v1",
            "metric_profile": "strict-v1",
            "ea": 0.5,
        }
        self.assertIs(metric_provenance(payload), MetricProvenance.STRICT_V1)
        self.assertIs(
            metric_provenance({"metric_profile": "strict-v1", "ea": 0.5}),
            MetricProvenance.LEGACY_NOTEBOOK,
        )

    def test_ace_summary_detail_consistency(self) -> None:
        summary = {
            "total_samples": 2,
            "test": {"ea_correct": 1, "pa_correct": 1},
        }
        details = [{"ea_pass": True, "pa_pass": True}, {"ea_pass": False, "pa_pass": False}]
        self.assertEqual(verify_summary_details(summary, details), [])
        summary["test"]["ea_correct"] = 2
        issues = verify_summary_details(summary, details)
        self.assertEqual(issues[0].code, "artifact_count_mismatch")

    def test_baseline_summary_detail_consistency(self) -> None:
        summary = {
            "total_records": 3,
            "processed": 2,
            "ea_match_count": 1,
            "pa_match_count": 1,
        }
        details = [
            {"skipped": False, "ea_match": True, "pa_match": True},
            {"skipped": False, "ea_match": False, "pa_match": False},
            {"skipped": True, "ea_match": False, "pa_match": False},
        ]
        self.assertEqual(verify_baseline_summary(summary, details), [])

    def test_tree_reports_legacy_without_failing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "summary.json").write_text(json.dumps({"EA": 0.5, "PA": 0.4}), encoding="utf-8")
            report = verify_artifact_tree(root)
        self.assertTrue(report.ok)
        self.assertEqual(report.legacy_metric_files, 1)
        self.assertTrue(any(issue.code == "legacy_metrics_present" for issue in report.issues))

    def test_tree_detects_corrupt_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "bad.jsonl").write_text('{"ok": true}\nnot-json\n', encoding="utf-8")
            report = verify_artifact_tree(root)
        self.assertFalse(report.ok)
        self.assertEqual(report.issues[0].code, "invalid_artifact")

    def test_tree_cross_checks_known_ace_pair(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "test_results.json").write_text(
                json.dumps(
                    {
                        "total_samples": 1,
                        "test": {"EA": 1.0, "PA": 0.0, "ea_correct": 1, "pa_correct": 0},
                    }
                ),
                encoding="utf-8",
            )
            (root / "test_detail.jsonl").write_text(
                json.dumps({"ea_pass": False, "pa_pass": False}) + "\n",
                encoding="utf-8",
            )
            report = verify_artifact_tree(root)
        self.assertFalse(report.ok)
        self.assertTrue(any(issue.code == "artifact_count_mismatch" for issue in report.issues))


if __name__ == "__main__":
    unittest.main()
