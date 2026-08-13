"""Unit tests for the strict, dependency-free FinQA DSL implementation."""

from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

# Keep the tests runnable with plain ``python -m unittest`` before installation.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ace_finqa.dsl import (  # noqa: E402
    DSLParseError,
    canonicalize_program_strict,
    execute_program,
    extract_program,
    normalize_program_legacy,
    parse_program,
)

SAMPLE_TABLE = [
    ["", "2023", "2022", "2021", "2020"],
    ["Net Sales", "$1,200", "(300)", "25%", "—"],
    ["effective tax rate", "26% ( 26 % )", "28% ( 28 % )", "(10%)", "-"],
    ["state taxes", "$ -19 ( 19 )", "$ 5", "1,000", "N/A"],
]


class ArithmeticExecutionTests(unittest.TestCase):
    def test_all_numeric_operations_and_references(self) -> None:
        result = execute_program(
            "add(2, const_3), subtract(#0, 1), multiply(#1, 2), divide(#2, 4), exp(#3, 2)"
        )
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.value, 4.0)
        self.assertEqual(len(result.steps), 5)
        self.assertIsNone(result.error)

    def test_percent_literals_are_divided_by_one_hundred(self) -> None:
        result = execute_program("subtract(35%, 13.7%)")
        self.assertTrue(result.ok, result.error)
        self.assertTrue(math.isclose(result.value, 0.213, abs_tol=1e-12))

    def test_greater_returns_finqa_yes_or_no(self) -> None:
        self.assertEqual(execute_program("greater(5, 4)").value, "yes")
        self.assertEqual(execute_program("greater(-2, -2)").value, "no")

    def test_yes_no_reference_is_not_silently_coerced_to_number(self) -> None:
        result = execute_program("greater(5, 4), add(#0, 1)")
        self.assertFalse(result.ok)
        self.assertEqual(result.error.code, "NON_NUMERIC_REFERENCE")
        self.assertIsNone(result.value)
        self.assertEqual(len(result.steps), 1)

    def test_negative_parenthetical_numeric_literal(self) -> None:
        result = execute_program("add((1,234), 34)")
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.value, -1200.0)

        currency_result = execute_program("add($ -20, 5)")
        self.assertTrue(currency_result.ok, currency_result.error)
        self.assertEqual(currency_result.value, -15.0)


class TableExecutionTests(unittest.TestCase):
    def test_table_operators_use_exact_row_labels(self) -> None:
        maximum = execute_program("table_max(net sales, none)", SAMPLE_TABLE)
        minimum = execute_program("table_min(net sales, none)", SAMPLE_TABLE)
        total = execute_program("table_sum(net sales, none)", SAMPLE_TABLE)
        average = execute_program("table_average(net sales, none)", SAMPLE_TABLE)

        self.assertEqual(maximum.value, 1200.0)
        self.assertEqual(minimum.value, -300.0)
        self.assertTrue(math.isclose(total.value, 900.25, abs_tol=1e-12))
        self.assertTrue(math.isclose(average.value, 300.0833333333333, abs_tol=1e-12))

    def test_finqa_display_annotations_and_percent_cells(self) -> None:
        average = execute_program("table_average(effective tax rate, none)", SAMPLE_TABLE)
        self.assertTrue(average.ok, average.error)
        self.assertTrue(math.isclose(average.value, 0.14666666666666667))

        total = execute_program("table_sum(state taxes, none)", SAMPLE_TABLE)
        self.assertTrue(total.ok, total.error)
        self.assertEqual(total.value, 986.0)

    def test_row_matching_is_case_insensitive_but_not_fuzzy(self) -> None:
        found = execute_program("table_sum(NET SALES, none)", SAMPLE_TABLE)
        self.assertTrue(found.ok, found.error)

        missing = execute_program("table_sum(sales, none)", SAMPLE_TABLE)
        self.assertFalse(missing.ok)
        self.assertEqual(missing.error.code, "TABLE_ROW_NOT_FOUND")

    def test_quoted_row_label_can_contain_comma(self) -> None:
        table = [["", "2023"], ["sales, net", "$2,500"]]
        result = execute_program('table_sum("sales, net", none)', table)
        self.assertTrue(result.ok, result.error)
        self.assertEqual(result.value, 2500.0)

    def test_duplicate_row_label_and_bad_cell_fail_closed(self) -> None:
        duplicate = [["", "2023"], ["sales", "1"], ["Sales", "2"]]
        result = execute_program("table_sum(sales, none)", duplicate)
        self.assertFalse(result.ok)
        self.assertEqual(result.error.code, "TABLE_ROW_AMBIGUOUS")

        invalid = [["", "2023"], ["sales", "not a number"]]
        result = execute_program("table_sum(sales, none)", invalid)
        self.assertFalse(result.ok)
        self.assertEqual(result.error.code, "INVALID_TABLE_CELL")


class FailClosedTests(unittest.TestCase):
    def assert_error(self, program: str, code: str) -> None:
        result = execute_program(program)
        self.assertFalse(result.ok)
        self.assertIsNone(result.value)
        self.assertIsNotNone(result.error)
        self.assertEqual(result.error.code, code)

    def test_unknown_operand_and_constant(self) -> None:
        self.assert_error("add(none, 1)", "INVALID_OPERAND")
        self.assert_error("add(const_999, 1)", "UNKNOWN_CONSTANT")

    def test_forward_and_out_of_range_references(self) -> None:
        self.assert_error("add(#0, 1)", "FORWARD_REFERENCE")
        self.assert_error("add(1, 2), multiply(#2, 4)", "FORWARD_REFERENCE")

    def test_division_by_zero(self) -> None:
        self.assert_error("divide(10, 0)", "DIVISION_BY_ZERO")
        self.assert_error("divide(10, 0%)", "DIVISION_BY_ZERO")

    def test_malformed_programs_do_not_return_partial_values(self) -> None:
        self.assert_error("add(1, 2),", "TRAILING_SEPARATOR")
        self.assert_error("add(1)", "INVALID_ARITY")
        self.assert_error("mystery(1, 2)", "UNKNOWN_OPERATION")
        self.assert_error("add(1, 2) trailing", "EXPECTED_STEP_SEPARATOR")

    def test_table_sentinel_is_strict(self) -> None:
        self.assert_error("table_sum(net sales, 0)", "INVALID_TABLE_SENTINEL")

    def test_error_is_structured(self) -> None:
        result = execute_program("add(#0, 1)")
        self.assertEqual(result.error.stage, "parse")
        self.assertEqual(result.error.step_index, 0)
        self.assertEqual(result.error.token, "#0")
        self.assertEqual(result.steps, ())


class ExtractionTests(unittest.TestCase):
    def test_extracts_fenced_plain_program(self) -> None:
        output = "Reasoning.\n```plaintext\nprogram: divide(637, 5.0)\n```"
        self.assertEqual(extract_program(output), "divide(637, 5.0)")

    def test_extracts_raw_fenced_multistep_program(self) -> None:
        output = "```\nadd(1, 2), multiply(#0, const_100)\n```"
        self.assertEqual(extract_program(output), "add(1, 2), multiply(#0, const_100)")

    def test_extracts_plain_and_json_outputs(self) -> None:
        self.assertEqual(extract_program("add(4, 5)"), "add(4, 5)")
        self.assertEqual(
            extract_program('{"answer": 3, "program": "subtract(5, 2)"}'),
            "subtract(5, 2)",
        )
        self.assertEqual(
            extract_program({"program": ["add(1, 2)", "divide(#0, 3)"]}),
            "add(1, 2), divide(#0, 3)",
        )

    def test_ignores_thinking_and_prefers_final_candidate(self) -> None:
        output = (
            "<think>Maybe add(100, 1).</think>\n"
            "An intermediate example is subtract(9, 3).\n"
            "program: multiply(6, 7)"
        )
        self.assertEqual(extract_program(output), "multiply(6, 7)")

    def test_returns_none_without_a_program(self) -> None:
        self.assertIsNone(extract_program("The answer is 42."))
        self.assertIsNone(extract_program(None))


class CanonicalizationTests(unittest.TestCase):
    def test_strict_canonicalization_preserves_reference_identity(self) -> None:
        program = "ADD(const_1, 35%), MULTIPLY(#0, 2.00)"
        self.assertEqual(
            canonicalize_program_strict(program),
            "add(1, 0.35), multiply(#0, 2)",
        )

    def test_strict_canonicalization_does_not_repair_forward_reference(self) -> None:
        with self.assertRaises(DSLParseError) as raised:
            canonicalize_program_strict("add(#9, 1)")
        self.assertEqual(raised.exception.code, "FORWARD_REFERENCE")

    def test_parser_exposes_typed_steps(self) -> None:
        steps = parse_program("add(1, 2), divide(#0, const_2)")
        self.assertEqual(steps[0].operation, "add")
        self.assertEqual(steps[1].arguments, ("#0", "const_2"))

    def test_legacy_normalizer_is_explicitly_compatible_and_permissive(self) -> None:
        # This documents the old behavior: it strips %, sorts commutative
        # operands, and rewrites invalid #9 into apparently valid #0.
        normalized = normalize_program_legacy("add(#9, const_1), multiply(#9, 35%)")
        self.assertEqual(normalized, "add(#0,1),multiply(#0,35)")


if __name__ == "__main__":
    unittest.main()
