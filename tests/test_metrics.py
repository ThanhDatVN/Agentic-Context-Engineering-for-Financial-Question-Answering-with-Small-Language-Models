from __future__ import annotations

import math
import unittest
from decimal import Decimal

from ace_finqa.metrics import (
    MetricAccumulator,
    Outcome,
    answers_equal_legacy_notebook,
    answers_equal_strict,
    classify_outcome,
)


class MetricTests(unittest.TestCase):
    def test_strict_rounds_finqa_answers_to_five_places(self) -> None:
        self.assertTrue(answers_equal_strict(1 / 3, 0.33333))
        self.assertTrue(answers_equal_strict(Decimal("0.189625"), 0.18962))
        self.assertTrue(answers_equal_strict(Decimal("0.128525"), 0.12853))
        self.assertTrue(answers_equal_strict(Decimal("0.178125"), 0.17813))
        self.assertFalse(answers_equal_strict(0.33339, 0.33333))

    def test_strict_rejects_one_percent_false_positive(self) -> None:
        self.assertTrue(answers_equal_legacy_notebook(17290, 17447))
        self.assertFalse(answers_equal_strict(17290, 17447))

    def test_strict_handles_yes_no_only(self) -> None:
        self.assertTrue(answers_equal_strict(" YES ", "yes"))
        self.assertFalse(answers_equal_strict("1", 1))
        self.assertFalse(answers_equal_strict("maybe", "maybe"))

    def test_strict_rejects_nan_infinity_bool_and_none(self) -> None:
        for value in (math.nan, math.inf, True, None):
            with self.subTest(value=value):
                self.assertFalse(answers_equal_strict(value, 1))

    def test_outcome_quadrants(self) -> None:
        self.assertIs(classify_outcome(True, True), Outcome.CORRECT)
        self.assertIs(classify_outcome(True, False), Outcome.LUCKY_GUESS)
        self.assertIs(classify_outcome(False, True), Outcome.EXEC_MISMATCH)
        self.assertIs(classify_outcome(False, False), Outcome.WRONG_REASONING)

    def test_accumulator_snapshot(self) -> None:
        accumulator = MetricAccumulator()
        accumulator.add(ea=True, pa=False, program_valid=True)
        accumulator.add(ea=False, pa=False, program_valid=False)
        snapshot = accumulator.snapshot()
        self.assertEqual(snapshot.total, 2)
        self.assertEqual(snapshot.execution_accuracy, 0.5)
        self.assertEqual(snapshot.invalid_programs, 1)
        self.assertEqual(snapshot.outcomes["lucky_guess"], 1)


if __name__ == "__main__":
    unittest.main()
