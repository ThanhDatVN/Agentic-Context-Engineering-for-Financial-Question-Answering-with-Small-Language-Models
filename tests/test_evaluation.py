import json
import tempfile
import unittest
from pathlib import Path

from ace_finqa.evaluation import (
    EVALUATION_SCHEMA,
    EvaluationError,
    evaluate_files,
    evaluate_predictions,
    load_predictions,
    normalize_predictions,
)


def sample(program, answer, *, sample_id="sample", table=None):
    return {
        "id": sample_id,
        "pre_text": ["evidence"],
        "post_text": [],
        "table": table or [["", "2019", "2020"], ["Revenue", "100", "120"]],
        "qa": {
            "question": f"question {sample_id}?",
            "program": program,
            "exe_ans": answer,
            "gold_inds": {},
        },
    }


class PredictionNormalizationTests(unittest.TestCase):
    def test_direct_program_wins_and_raw_output_is_extracted_only_as_fallback(self):
        rows = normalize_predictions(
            [
                {
                    "idx": 0,
                    "pred_prog": "add(1, 1)",
                    "pred_text": "```plaintext\nsubtract(2, 1)\n```",
                },
                {"idx": "1", "pred_text": "answer:\n```plaintext\nmultiply(50%, 200)\n```"},
            ],
            dataset_size=2,
        )
        self.assertEqual(rows[0].program, "add(1, 1)")
        self.assertFalse(rows[0].extracted)
        self.assertEqual(rows[1].program, "multiply(50%, 200)")
        self.assertTrue(rows[1].extracted)

    def test_missing_duplicate_and_out_of_range_indices_fail(self):
        with self.assertRaisesRegex(EvaluationError, "missing indices"):
            normalize_predictions([{"idx": 0, "pred_prog": "add(1,1)"}], dataset_size=2)
        with self.assertRaisesRegex(EvaluationError, "Duplicate"):
            normalize_predictions([{"idx": 0}, {"idx": 0}], dataset_size=2, require_complete=False)
        with self.assertRaisesRegex(EvaluationError, "outside"):
            normalize_predictions([{"idx": 2}], dataset_size=2, require_complete=False)

    def test_explicit_partial_evaluation_preserves_true_indices(self):
        rows = normalize_predictions(
            [{"idx": 2, "pred_prog": "add(1,1)"}],
            dataset_size=3,
            require_complete=False,
        )
        self.assertEqual([row.index for row in rows], [2])

    def test_loads_supported_json_shapes_and_rejects_unknown_extension(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            nested = root / "predictions.json"
            nested.write_text(
                json.dumps({"predictions": [{"pred_prog": "add(1,1)"}]}),
                encoding="utf-8",
            )
            self.assertEqual(len(load_predictions(nested)), 1)
            unknown = root / "predictions.txt"
            unknown.write_text("add(1,1)", encoding="utf-8")
            with self.assertRaisesRegex(EvaluationError, "Unsupported"):
                load_predictions(unknown)


class StrictEvaluationTests(unittest.TestCase):
    def test_recomputes_all_outcomes_percent_table_and_invalid_programs(self):
        samples = [
            sample("add(1, 1)", 2, sample_id="correct"),
            sample("multiply(50%, 200)", 100, sample_id="lucky"),
            sample("table_sum(Revenue, none)", 221, sample_id="mismatch"),
            sample("divide(1, 2)", 0.5, sample_id="invalid"),
        ]
        predictions = [
            {"pred_prog": "add(1, 1)", "ea_match": False, "pa_match": False},
            {"pred_text": "```plaintext\ndivide(200, 2)\n```"},
            {"pred_prog": "table_sum(Revenue, none)"},
            {"pred_prog": "divide(1, 0)"},
        ]
        report = evaluate_predictions(samples, predictions)
        payload = report.to_dict(include_details=True)

        self.assertEqual(payload["schema"], EVALUATION_SCHEMA)
        self.assertEqual(payload["metric_profile"], "strict-v1")
        self.assertEqual(payload["counts"]["total"], 4)
        self.assertEqual(payload["counts"]["execution_correct"], 2)
        self.assertEqual(payload["counts"]["program_correct"], 2)
        self.assertEqual(payload["counts"]["invalid_programs"], 1)
        self.assertEqual(
            payload["counts"]["outcomes"],
            {"correct": 1, "exec_mismatch": 1, "lucky_guess": 1, "wrong_reasoning": 1},
        )
        self.assertTrue(payload["details"][1]["program_extracted"])
        self.assertEqual(payload["details"][1]["predicted_answer"], 100.0)
        self.assertEqual(payload["details"][2]["predicted_answer"], 220.0)
        self.assertEqual(payload["details"][3]["error"]["code"], "DIVISION_BY_ZERO")
        self.assertIn("did not match qa.exe_ans", payload["warnings"][0])

    def test_strict_profile_rejects_notebook_one_percent_tolerance(self):
        report = evaluate_predictions(
            [sample("divide(1005, 1000)", 1.0)],
            [{"pred_prog": "divide(1005, 1000)"}],
        )
        self.assertEqual(report.counts["execution_correct"], 0)
        self.assertEqual(report.counts["program_correct"], 1)

    def test_no_program_is_a_structured_fail_closed_record(self):
        report = evaluate_predictions([sample("add(1, 1)", 2)], [None])
        detail = report.details[0]
        self.assertFalse(detail.program_valid)
        self.assertEqual(detail.error["code"], "NO_PROGRAM")

    def test_partial_report_has_explicit_coverage_and_denominator(self):
        samples = [
            sample("add(1,1)", 2, sample_id="first"),
            sample("add(2,2)", 4, sample_id="second"),
        ]
        report = evaluate_predictions(
            samples,
            [{"idx": 1, "pred_prog": "add(2,2)"}],
            require_complete=False,
        )
        self.assertEqual(report.dataset_records, 2)
        self.assertEqual(report.counts["total"], 1)
        self.assertEqual(report.coverage, 0.5)
        self.assertIn("Partial evaluation", report.warnings[0])

    def test_file_evaluation_records_content_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dataset = root / "test.json"
            predictions = root / "predictions.jsonl"
            dataset.write_text(json.dumps([sample("add(1,1)", 2)]), encoding="utf-8")
            predictions.write_text(
                json.dumps({"idx": 0, "pred_prog": "add(1,1)"}) + "\n",
                encoding="utf-8",
            )
            report = evaluate_files(dataset, predictions)
            self.assertEqual(report.dataset_path, dataset.as_posix())
            self.assertEqual(report.predictions_path, predictions.as_posix())
            self.assertEqual(len(report.dataset_sha256), 64)
            self.assertEqual(len(report.predictions_sha256), 64)
            self.assertEqual(report.counts["execution_correct"], 1)


if __name__ == "__main__":
    unittest.main()
