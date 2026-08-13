"""Metric profiles and outcome accounting for FinQA evaluation."""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any


class MetricProfile(str, Enum):
    """Explicit metric semantics.

    ``LEGACY_NOTEBOOK`` exists only to label historical values. New evaluations
    must use ``STRICT_V1`` unless a caller deliberately opts into reproducing the
    notebook's broad one-percent relative tolerance.
    """

    STRICT_V1 = "strict-v1"
    LEGACY_NOTEBOOK = "legacy-notebook"


class Outcome(str, Enum):
    CORRECT = "correct"
    LUCKY_GUESS = "lucky_guess"
    EXEC_MISMATCH = "exec_mismatch"
    WRONG_REASONING = "wrong_reasoning"


def _finite_decimal(value: Any) -> Decimal | None:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    try:
        result = Decimal(str(value))
    except InvalidOperation:
        return None
    return result if result.is_finite() else None


def answers_equal_strict(predicted: Any, gold: Any, *, decimal_places: int = 5) -> bool:
    """Compare valid answers after deterministic decimal quantization.

    FinQA's reference evaluator applies ``round(float_value, 5)`` before exact
    comparison. This profile mirrors that binary-float behavior without the
    notebook's permissive 1% relative band. Strings are limited to
    case-insensitive ``yes``/``no``.
    """

    if isinstance(predicted, str) or isinstance(gold, str):
        left = str(predicted).strip().casefold()
        right = str(gold).strip().casefold()
        return left in {"yes", "no"} and left == right
    left_number = _finite_decimal(predicted)
    right_number = _finite_decimal(gold)
    if left_number is None or right_number is None:
        return False
    try:
        left_float = float(left_number)
        right_float = float(right_number)
        if not math.isfinite(left_float) or not math.isfinite(right_float):
            return False
        return round(left_float, decimal_places) == round(right_float, decimal_places)
    except (OverflowError, ValueError):
        return False


def answers_equal_legacy_notebook(
    predicted: Any,
    gold: Any,
    *,
    relative_tolerance: float = 0.01,
) -> bool:
    """Reproduce the notebook answer comparison for audit-only use."""

    if predicted is None or gold is None:
        return False
    if isinstance(predicted, str) or isinstance(gold, str):
        return str(predicted).strip().casefold() == str(gold).strip().casefold()
    left = _finite_decimal(predicted)
    right = _finite_decimal(gold)
    if left is None or right is None:
        return False
    p = float(left)
    g = float(right)
    if g == 0:
        return abs(p) <= relative_tolerance
    return abs(p - g) / abs(g) <= relative_tolerance


def classify_outcome(execution_accuracy: bool, program_accuracy: bool) -> Outcome:
    """Classify the EA/PA quadrant using the notebook's established labels."""

    if execution_accuracy and program_accuracy:
        return Outcome.CORRECT
    if execution_accuracy:
        return Outcome.LUCKY_GUESS
    if program_accuracy:
        return Outcome.EXEC_MISMATCH
    return Outcome.WRONG_REASONING


@dataclass(frozen=True)
class MetricCounts:
    total: int
    execution_correct: int
    program_correct: int
    invalid_programs: int
    outcomes: dict[str, int]

    @property
    def execution_accuracy(self) -> float:
        return self.execution_correct / self.total if self.total else 0.0

    @property
    def program_accuracy(self) -> float:
        return self.program_correct / self.total if self.total else 0.0

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["execution_accuracy"] = round(self.execution_accuracy, 6)
        result["program_accuracy"] = round(self.program_accuracy, 6)
        return result


class MetricAccumulator:
    """Small mutable accumulator with an immutable public snapshot."""

    def __init__(self) -> None:
        self.total = 0
        self.execution_correct = 0
        self.program_correct = 0
        self.invalid_programs = 0
        self.outcomes: Counter[str] = Counter()

    def add(self, *, ea: bool, pa: bool, program_valid: bool) -> Outcome:
        outcome = classify_outcome(ea, pa)
        self.total += 1
        self.execution_correct += int(ea)
        self.program_correct += int(pa)
        self.invalid_programs += int(not program_valid)
        self.outcomes[outcome.value] += 1
        return outcome

    def snapshot(self) -> MetricCounts:
        return MetricCounts(
            total=self.total,
            execution_correct=self.execution_correct,
            program_correct=self.program_correct,
            invalid_programs=self.invalid_programs,
            outcomes=dict(sorted(self.outcomes.items())),
        )
