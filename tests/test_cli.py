import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from ace_finqa.cli import main


def fixture_sample():
    return {
        "pre_text": [],
        "post_text": [],
        "table": [["", "value"], ["Revenue", "2"]],
        "qa": {
            "question": "What is one plus one?",
            "program": "add(1, 1)",
            "exe_ans": 2,
            "gold_inds": {},
        },
    }


class CLITests(unittest.TestCase):
    def invoke(self, arguments):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main(arguments)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_data_summary_command(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for split in ("train", "dev", "test"):
                (root / f"{split}.json").write_text(
                    json.dumps([fixture_sample()]), encoding="utf-8"
                )
            code, stdout, stderr = self.invoke(
                ["data-summary", "--data-dir", str(root), "--no-enforce-size"]
            )
            payload = json.loads(stdout)
            self.assertEqual(code, 0)
            self.assertEqual(stderr, "")
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["splits"]["test"]["samples"], 1)

    def test_evaluate_command_writes_strict_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dataset = root / "test.json"
            predictions = root / "predictions.json"
            output = root / "report.json"
            dataset.write_text(json.dumps([fixture_sample()]), encoding="utf-8")
            predictions.write_text(
                json.dumps([{"pred_text": "```plaintext\nadd(1, 1)\n```"}]),
                encoding="utf-8",
            )
            code, stdout, stderr = self.invoke(
                [
                    "evaluate",
                    "--data-file",
                    str(dataset),
                    "--predictions",
                    str(predictions),
                    "--include-details",
                    "--output",
                    str(output),
                ]
            )
            payload = json.loads(stdout)
            stored = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(code, 0)
            self.assertEqual(stderr, "")
            self.assertEqual(payload, stored)
            self.assertEqual(payload["metric_profile"], "strict-v1")
            self.assertEqual(payload["counts"]["execution_correct"], 1)

    def test_evaluate_command_reports_incomplete_predictions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dataset = root / "test.json"
            predictions = root / "predictions.json"
            dataset.write_text(json.dumps([fixture_sample(), fixture_sample()]), encoding="utf-8")
            predictions.write_text(json.dumps([{"pred_prog": "add(1,1)"}]), encoding="utf-8")
            code, stdout, stderr = self.invoke(
                ["evaluate", str(dataset), "--predictions", str(predictions)]
            )
            self.assertEqual(code, 2)
            self.assertEqual(stdout, "")
            self.assertIn("missing indices", json.loads(stderr)["message"])

    def test_verify_repo_command_returns_machine_readable_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data_dir = root / "custom-data"
            results_dir = root / "custom-results"
            data_dir.mkdir()
            results_dir.mkdir()
            for split in ("train", "dev", "test"):
                (data_dir / f"{split}.json").write_text(
                    json.dumps([fixture_sample()]), encoding="utf-8"
                )
            code, stdout, stderr = self.invoke(
                [
                    "verify-repo",
                    str(root),
                    "--data-dir",
                    "custom-data",
                    "--results-dir",
                    "custom-results",
                ]
            )
            payload = json.loads(stdout)
            self.assertEqual(code, 1)
            self.assertEqual(stderr, "")
            self.assertEqual(payload["schema"], "ace-finqa.repository-verification.v1")
            self.assertFalse(payload["ok"])
            self.assertNotIn("missing_results", {issue["code"] for issue in payload["issues"]})


if __name__ == "__main__":
    unittest.main()
