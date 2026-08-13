from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from ace_finqa.data import (
    DatasetError,
    load_split,
    summarize_data_dir,
    summarize_samples,
    summarize_split,
    validate_samples,
)


def sample(*, sample_id: str = "s1") -> dict:
    return {
        "id": sample_id,
        "pre_text": ["Revenue increased."],
        "post_text": ["All values are in millions."],
        "table": [["", "2020", "2021"], ["revenue", "$ 100", "$ 120"]],
        "qa": {
            "question": "What was the change in revenue?",
            "program": "subtract(120, 100)",
            "exe_ans": 20.0,
            "gold_inds": {"table_1": "revenue"},
        },
    }


class DataValidationTests(unittest.TestCase):
    def test_valid_fixture(self) -> None:
        result = validate_samples([sample()], split="test")
        self.assertTrue(result.ok)
        self.assertEqual(result.valid_count, 1)

    def test_expected_size_is_explicit(self) -> None:
        relaxed = validate_samples([sample()], split="test", enforce_expected_size=False)
        strict = validate_samples([sample()], split="test", enforce_expected_size=True)
        self.assertTrue(relaxed.ok)
        self.assertFalse(strict.ok)
        self.assertEqual(strict.issues[0].code, "unexpected_split_size")

    def test_reports_schema_and_duplicate_ids(self) -> None:
        broken = sample()
        broken["qa"] = {"question": "", "program": "", "gold_inds": []}
        result = validate_samples([sample(), broken], split=None)
        codes = {issue.code for issue in result.issues}
        self.assertIn("duplicate_id", codes)
        self.assertIn("invalid_question", codes)
        self.assertIn("invalid_program", codes)
        self.assertIn("missing_answer", codes)
        self.assertIn("invalid_gold_inds", codes)

    def test_summary_counts_operations_and_answer_types(self) -> None:
        yes = sample(sample_id="s2")
        yes["qa"] = {
            "question": "Was revenue larger?",
            "program": "greater(120, 100)",
            "exe_ans": "yes",
            "gold_inds": {"table_1": "revenue"},
        }
        summary = summarize_samples([sample(), yes], split="test")
        self.assertEqual(summary.samples, 2)
        self.assertEqual(summary.numeric_answers, 1)
        self.assertEqual(summary.string_answers, 1)
        self.assertEqual(summary.operation_counts, {"greater": 1, "subtract": 1})
        self.assertEqual(summary.program_steps, {"1": 2})

    def test_load_and_summarize_split(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.json"
            path.write_text(json.dumps([sample()]), encoding="utf-8")
            loaded = load_split(path)
            summary, validation = summarize_split(path)
        self.assertEqual(loaded[0]["id"], "s1")
        self.assertTrue(validation.ok)
        self.assertEqual(len(summary.sha256 or ""), 64)

    def test_rejects_non_array_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text("{}", encoding="utf-8")
            with self.assertRaises(DatasetError):
                load_split(path)

    def test_data_directory_reports_missing_splits(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "train.json").write_text(json.dumps([sample()]), encoding="utf-8")
            summary = summarize_data_dir(root, enforce_expected_size=False)
        self.assertFalse(summary["ok"])
        self.assertEqual(summary["splits"]["dev"]["issues"][0]["code"], "missing_split")


if __name__ == "__main__":
    unittest.main()
