"""Strict, dependency-free parser and executor for the FinQA DSL.

The original research notebooks bundled parsing, execution, and a permissive
program normalizer in one cell.  That implementation silently converted bad
operands to zero and treated table arguments as column names.  This module is
deliberately fail-closed: malformed syntax, unknown constants, invalid or
forward references, missing table rows, and undefined arithmetic all produce
an :class:`ExecutionResult` with a structured error.

Only the small operation vocabulary used by FinQA is supported.  The module
uses Python's standard library and is suitable for CPU-only evaluation and CI.
"""

from __future__ import annotations

import ast
import json
import math
import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

ARITHMETIC_OPERATIONS = frozenset({"add", "subtract", "multiply", "divide", "greater", "exp"})
TABLE_OPERATIONS = frozenset({"table_max", "table_min", "table_average", "table_sum"})
SUPPORTED_OPERATIONS = ARITHMETIC_OPERATIONS | TABLE_OPERATIONS

# This is the constant vocabulary used by the FinQA data and the original
# notebooks.  Constants are enumerated intentionally: accepting arbitrary
# ``const_N`` tokens would hide generation errors.
FINQA_CONSTANTS: Mapping[str, float] = {
    "const_1": 1.0,
    "const_2": 2.0,
    "const_3": 3.0,
    "const_4": 4.0,
    "const_5": 5.0,
    "const_6": 6.0,
    "const_7": 7.0,
    "const_8": 8.0,
    "const_9": 9.0,
    "const_10": 10.0,
    "const_12": 12.0,
    "const_100": 100.0,
    "const_1000": 1_000.0,
    "const_10000": 10_000.0,
    "const_100000": 100_000.0,
    "const_1000000": 1_000_000.0,
    "const_1000000000": 1_000_000_000.0,
    "const_m1": -1.0,
}


@dataclass(frozen=True)
class DSLError:
    """Machine-readable information about a parse or execution failure."""

    stage: str
    code: str
    message: str
    step_index: int | None = None
    token: str | None = None
    position: int | None = None


class DSLParseError(ValueError):
    """Raised by strict parser/canonicalizer APIs.

    ``execute_program`` catches this exception and returns its ``detail`` in an
    :class:`ExecutionResult`; callers using ``parse_program`` directly can
    inspect the same stable fields on the exception.
    """

    def __init__(
        self,
        code: str,
        message: str,
        *,
        step_index: int | None = None,
        token: str | None = None,
        position: int | None = None,
    ) -> None:
        self.detail = DSLError(
            stage="parse",
            code=code,
            message=message,
            step_index=step_index,
            token=token,
            position=position,
        )
        self.code = code
        self.step_index = step_index
        self.token = token
        self.position = position
        super().__init__(message)


class DSLExecutionError(RuntimeError):
    """Internal fail-closed execution exception with structured details."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        step_index: int | None = None,
        token: str | None = None,
    ) -> None:
        self.detail = DSLError(
            stage="execution",
            code=code,
            message=message,
            step_index=step_index,
            token=token,
        )
        self.code = code
        self.step_index = step_index
        self.token = token
        super().__init__(message)


@dataclass(frozen=True)
class ProgramStep:
    """One parsed FinQA operation."""

    index: int
    operation: str
    arguments: tuple[str, str]


@dataclass(frozen=True)
class ExecutionStep:
    """Trace information for one successfully executed operation."""

    index: int
    operation: str
    arguments: tuple[str, str]
    resolved_arguments: tuple[Any, Any]
    value: float | str


@dataclass(frozen=True)
class ExecutionResult:
    """Result returned for both successful and failed executions."""

    ok: bool
    value: float | str | None
    error: DSLError | None
    program: str | None
    steps: tuple[ExecutionStep, ...] = ()


_IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_REFERENCE_RE = re.compile(r"#(0|[1-9][0-9]*)\Z")
_CONSTANT_TOKEN_RE = re.compile(r"const_[A-Za-z0-9_]+\Z", re.IGNORECASE)
_CURRENCY_CHARS = "$£€¥"
_NUMBER_BODY = r"(?:\d{1,3}(?:,\d{3})+|\d+(?:\.\d*)?|\.\d+)"
_STRICT_NUMBER_RE = re.compile(
    rf"(?P<sign>[+-]?)\s*(?P<currency>[{re.escape(_CURRENCY_CHARS)}]?)\s*"
    rf"(?P<number>{_NUMBER_BODY})(?P<exponent>[eE][+-]?\d+)?\s*"
    r"(?P<percent>%?)\Z"
)
_CELL_NUMBER_RE = re.compile(
    rf"(?P<sign>[+-]?)\s*(?P<currency>[{re.escape(_CURRENCY_CHARS)}]?)\s*"
    rf"(?P<number>{_NUMBER_BODY})(?P<exponent>[eE][+-]?\d+)?\s*"
    r"(?P<percent>%?)"
)
_MISSING_TABLE_CELLS = frozenset(
    {"", "-", "--", "—", "–", "n/a", "na", "n.m.", "nm", "none", "null"}
)
_DSL_START_RE = re.compile(
    r"\b(?:add|subtract|multiply|divide|greater|exp|table_max|table_min|"
    r"table_average|table_sum)\s*\(",
    re.IGNORECASE,
)
_FENCED_BLOCK_RE = re.compile(r"```(?:[A-Za-z0-9_+.-]+)?[ \t]*\r?\n?(.*?)```", re.DOTALL)


def _parse_error(
    code: str,
    message: str,
    *,
    step_index: int | None = None,
    token: str | None = None,
    position: int | None = None,
) -> DSLParseError:
    return DSLParseError(
        code,
        message,
        step_index=step_index,
        token=token,
        position=position,
    )


def _split_arguments(body: str, *, step_index: int, body_position: int) -> tuple[str, str]:
    """Split two arguments while respecting quotes and accounting parens."""

    comma_positions: list[int] = []
    nested_depth = 0
    quote: str | None = None
    escaped = False

    for offset, char in enumerate(body):
        if quote is not None:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue

        if char in {'"', "'"}:
            quote = char
        elif char == "(":
            nested_depth += 1
        elif char == ")":
            if nested_depth == 0:
                raise _parse_error(
                    "UNEXPECTED_PARENTHESIS",
                    "Unexpected ')' in operation arguments.",
                    step_index=step_index,
                    position=body_position + offset,
                )
            nested_depth -= 1
        elif char == "," and nested_depth == 0:
            comma_positions.append(offset)

    if quote is not None:
        raise _parse_error(
            "UNTERMINATED_STRING",
            "Unterminated quoted argument.",
            step_index=step_index,
            position=body_position + len(body),
        )
    if nested_depth:
        raise _parse_error(
            "UNBALANCED_PARENTHESES",
            "Unbalanced parentheses in operation arguments.",
            step_index=step_index,
            position=body_position + len(body),
        )
    if len(comma_positions) != 1:
        raise _parse_error(
            "INVALID_ARITY",
            "FinQA operations require exactly two arguments.",
            step_index=step_index,
            token=body,
            position=body_position,
        )

    split_at = comma_positions[0]
    left, right = body[:split_at].strip(), body[split_at + 1 :].strip()
    if not left or not right:
        raise _parse_error(
            "EMPTY_ARGUMENT",
            "Operation arguments must not be empty.",
            step_index=step_index,
            token=body,
            position=body_position + split_at,
        )
    return left, right


def _find_closing_parenthesis(source: str, open_position: int, *, step_index: int) -> int:
    depth = 1
    quote: str | None = None
    escaped = False
    for position in range(open_position + 1, len(source)):
        char = source[position]
        if quote is not None:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in {'"', "'"}:
            quote = char
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return position

    code = "UNTERMINATED_STRING" if quote is not None else "UNBALANCED_PARENTHESES"
    message = (
        "Unterminated quoted argument."
        if quote is not None
        else "Operation is missing its closing parenthesis."
    )
    raise _parse_error(
        code,
        message,
        step_index=step_index,
        position=len(source),
    )


def _decode_row_label(token: str, *, step_index: int) -> str:
    stripped = token.strip()
    if stripped[:1] in {'"', "'"} or stripped[-1:] in {'"', "'"}:
        if len(stripped) < 2 or stripped[0] != stripped[-1]:
            raise _parse_error(
                "UNTERMINATED_STRING",
                "Table row label has mismatched quotes.",
                step_index=step_index,
                token=token,
            )
        try:
            value = ast.literal_eval(stripped)
        except (SyntaxError, ValueError) as exc:
            raise _parse_error(
                "INVALID_ROW_LABEL",
                "Table row label is not a valid quoted string.",
                step_index=step_index,
                token=token,
            ) from exc
        if not isinstance(value, str):
            raise _parse_error(
                "INVALID_ROW_LABEL",
                "Quoted table row label must decode to text.",
                step_index=step_index,
                token=token,
            )
        stripped = value

    label = " ".join(stripped.split())
    if not label:
        raise _parse_error(
            "EMPTY_ROW_LABEL",
            "Table operation requires a non-empty row label.",
            step_index=step_index,
            token=token,
        )
    return label


def _decimal_from_number_match(match: re.Match[str]) -> Decimal:
    number_text = match.group("number").replace(",", "")
    exponent = match.group("exponent") or ""
    sign = match.group("sign") or ""
    try:
        value = Decimal(f"{sign}{number_text}{exponent}")
    except InvalidOperation as exc:  # Defensive; the regex already constrains it.
        raise ValueError("invalid numeric value") from exc
    if match.group("percent"):
        value /= Decimal(100)
    if not value.is_finite():
        raise ValueError("non-finite numeric value")
    return value


def _normalize_currency_sign(text: str) -> str:
    """Normalize FinQA's ``$ -12`` display form to regex-friendly ``-$12``."""

    return re.sub(
        rf"^([{re.escape(_CURRENCY_CHARS)}])\s*([+-])\s*",
        lambda match: f"{match.group(2)}{match.group(1)}",
        text,
    )


def _parse_numeric_literal(token: str) -> float:
    stripped = unicodedata.normalize("NFKC", token).strip()
    stripped = stripped.replace("−", "-").replace("–", "-")
    stripped = _normalize_currency_sign(stripped)

    # Accounting-negative literals such as ``(1,234)`` are accepted.  Nested
    # parens are already protected by the program argument splitter.
    negative_parentheses = False
    currency_prefix = ""
    if stripped[:1] in _CURRENCY_CHARS and stripped[1:].lstrip().startswith("("):
        currency_prefix = stripped[0]
        stripped = stripped[1:].strip()
    if stripped.startswith("(") and stripped.endswith(")"):
        negative_parentheses = True
        stripped = f"{currency_prefix}{stripped[1:-1].strip()}"

    match = _STRICT_NUMBER_RE.fullmatch(stripped)
    if match is None:
        raise ValueError(f"not a numeric literal: {token!r}")
    value = _decimal_from_number_match(match)
    if negative_parentheses:
        value = -abs(value)
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("numeric literal is outside the finite float range")
    return result


def _validate_program_step(step: ProgramStep) -> None:
    left, right = step.arguments
    if step.operation in TABLE_OPERATIONS:
        _decode_row_label(left, step_index=step.index)
        if right.casefold() != "none":
            raise _parse_error(
                "INVALID_TABLE_SENTINEL",
                "The second argument of a table operation must be 'none'.",
                step_index=step.index,
                token=right,
            )
        return

    for token in (left, right):
        reference = _REFERENCE_RE.fullmatch(token)
        if reference is not None:
            referenced_index = int(reference.group(1))
            if referenced_index >= step.index:
                raise _parse_error(
                    "FORWARD_REFERENCE",
                    f"Reference {token!r} does not name an earlier step.",
                    step_index=step.index,
                    token=token,
                )
            continue

        folded = token.casefold()
        if _CONSTANT_TOKEN_RE.fullmatch(token):
            if folded not in FINQA_CONSTANTS:
                raise _parse_error(
                    "UNKNOWN_CONSTANT",
                    f"Unknown FinQA constant {token!r}.",
                    step_index=step.index,
                    token=token,
                )
            continue

        try:
            _parse_numeric_literal(token)
        except ValueError as exc:
            raise _parse_error(
                "INVALID_OPERAND",
                f"Operand {token!r} is not a number, known constant, or prior reference.",
                step_index=step.index,
                token=token,
            ) from exc


def parse_program(program: str) -> tuple[ProgramStep, ...]:
    """Parse and statically validate a strict FinQA program.

    The parser never repairs references or drops malformed commands.  It raises
    :class:`DSLParseError` with a structured ``detail`` on failure.
    """

    if not isinstance(program, str):
        raise _parse_error("INVALID_PROGRAM_TYPE", "Program must be text.")
    if not program.strip():
        raise _parse_error("EMPTY_PROGRAM", "Program must not be empty.")

    position = 0
    steps: list[ProgramStep] = []
    length = len(program)

    while position < length:
        while position < length and program[position].isspace():
            position += 1
        if position >= length:
            break

        identifier_match = _IDENTIFIER_RE.match(program, position)
        if identifier_match is None:
            raise _parse_error(
                "EXPECTED_OPERATION",
                "Expected a FinQA operation name.",
                step_index=len(steps),
                token=program[position : position + 20],
                position=position,
            )
        operation = identifier_match.group(0).casefold()
        if operation not in SUPPORTED_OPERATIONS:
            raise _parse_error(
                "UNKNOWN_OPERATION",
                f"Unsupported FinQA operation {identifier_match.group(0)!r}.",
                step_index=len(steps),
                token=identifier_match.group(0),
                position=position,
            )
        position = identifier_match.end()
        while position < length and program[position].isspace():
            position += 1
        if position >= length or program[position] != "(":
            raise _parse_error(
                "EXPECTED_OPEN_PARENTHESIS",
                f"Operation {operation!r} must be followed by '('.",
                step_index=len(steps),
                token=operation,
                position=position,
            )

        close_position = _find_closing_parenthesis(program, position, step_index=len(steps))
        body_position = position + 1
        arguments = _split_arguments(
            program[body_position:close_position],
            step_index=len(steps),
            body_position=body_position,
        )
        step = ProgramStep(len(steps), operation, arguments)
        _validate_program_step(step)
        steps.append(step)
        position = close_position + 1

        while position < length and program[position].isspace():
            position += 1
        if position >= length:
            break
        if program[position] != ",":
            raise _parse_error(
                "EXPECTED_STEP_SEPARATOR",
                "Operations must be separated by a comma.",
                step_index=len(steps),
                token=program[position : position + 20],
                position=position,
            )
        position += 1
        separator_position = position - 1
        while position < length and program[position].isspace():
            position += 1
        if position >= length:
            raise _parse_error(
                "TRAILING_SEPARATOR",
                "Program must not end with a step separator.",
                step_index=len(steps),
                position=separator_position,
            )

    if not steps:  # Kept defensive if whitespace handling changes in future.
        raise _parse_error("EMPTY_PROGRAM", "Program must contain an operation.")
    return tuple(steps)


def _format_decimal(value: Decimal) -> str:
    if value.is_zero():
        return "0"
    rendered = format(value.normalize(), "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered


def _canonical_numeric_operand(token: str) -> str:
    folded = token.casefold()
    if folded in FINQA_CONSTANTS:
        return _format_decimal(Decimal(str(FINQA_CONSTANTS[folded])))
    if _REFERENCE_RE.fullmatch(token):
        return f"#{int(token[1:])}"

    normalized = unicodedata.normalize("NFKC", token).strip()
    normalized = normalized.replace("−", "-").replace("–", "-")
    normalized = _normalize_currency_sign(normalized)
    negative_parentheses = False
    currency_prefix = ""
    if normalized[:1] in _CURRENCY_CHARS and normalized[1:].lstrip().startswith("("):
        currency_prefix = normalized[0]
        normalized = normalized[1:].strip()
    if normalized.startswith("(") and normalized.endswith(")"):
        negative_parentheses = True
        normalized = f"{currency_prefix}{normalized[1:-1].strip()}"
    match = _STRICT_NUMBER_RE.fullmatch(normalized)
    if match is None:  # The strict parser has already validated this token.
        raise AssertionError(f"validated operand no longer parses: {token!r}")
    value = _decimal_from_number_match(match)
    if negative_parentheses:
        value = -abs(value)
    return _format_decimal(value)


def _canonical_row_label(token: str, *, step_index: int) -> str:
    label = _decode_row_label(token, step_index=step_index).casefold()
    # Quote only when punctuation would make the canonical form ambiguous to
    # the parser.  Ordinary FinQA labels remain human-readable.
    if any(character in label for character in ",()\"'"):
        return json.dumps(label, ensure_ascii=False)
    return label


def _canonicalize_steps(steps: Sequence[ProgramStep]) -> str:
    commands: list[str] = []
    for step in steps:
        left, right = step.arguments
        if step.operation in TABLE_OPERATIONS:
            canonical_left = _canonical_row_label(left, step_index=step.index)
            canonical_right = "none"
        else:
            canonical_left = _canonical_numeric_operand(left)
            canonical_right = _canonical_numeric_operand(right)
        commands.append(f"{step.operation}({canonical_left}, {canonical_right})")
    return ", ".join(commands)


def canonicalize_program_strict(program: str) -> str:
    """Validate a program and return a semantics-preserving canonical form.

    Unlike the legacy notebook normalizer, this function never renumbers a
    reference or reorders operands.  Invalid/forward references raise
    :class:`DSLParseError` rather than being made to look valid.
    """

    return _canonicalize_steps(parse_program(program))


def _normalize_label(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value)).casefold()
    return " ".join(text.split())


def _parse_table_cell(cell: Any) -> float | None:
    if cell is None:
        return None
    if isinstance(cell, bool):
        raise ValueError("boolean table cell is not numeric")
    if isinstance(cell, (int, float, Decimal)):
        value = float(cell)
        if not math.isfinite(value):
            raise ValueError("non-finite table cell")
        return value

    text = unicodedata.normalize("NFKC", str(cell)).strip()
    text = text.replace("−", "-").replace("–", "-")
    text = _normalize_currency_sign(text)
    if text.casefold() in _MISSING_TABLE_CELLS:
        return None

    # Full accounting-negative cells: ``(1,234)``, ``($ 1,234)``, or
    # ``$(1,234)``.  Parentheses appearing *after* a leading number in FinQA
    # (for example ``26% ( 26 % )``) are display annotations, not a sign.
    negative_parentheses = False
    currency_prefix = ""
    candidate = text
    if candidate[:1] in _CURRENCY_CHARS and candidate[1:].lstrip().startswith("("):
        currency_prefix = candidate[0]
        candidate = candidate[1:].strip()
    if candidate.startswith("(") and candidate.endswith(")"):
        negative_parentheses = True
        candidate = f"{currency_prefix}{candidate[1:-1].strip()}"

    match = _CELL_NUMBER_RE.match(candidate)
    if match is None:
        raise ValueError(f"table cell is not numeric: {cell!r}")

    remainder = candidate[match.end() :].strip()
    # FinQA tables often repeat the displayed value in parentheses.  Permit
    # such annotations (and simple footnote markers), but do not accept an
    # arbitrary text prefix as a number.
    if remainder and not re.fullmatch(r"(?:\([^()]*\)|\[[^\[\]]*\]|[*†‡])+", remainder):
        raise ValueError(f"unsupported text after numeric table cell: {cell!r}")

    value = _decimal_from_number_match(match)
    if negative_parentheses:
        value = -abs(value)
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("table cell is outside the finite float range")
    return result


def _table_row_values(
    table: Sequence[Sequence[Any]] | None,
    row_token: str,
    *,
    step_index: int,
) -> tuple[str, tuple[float, ...]]:
    if table is None or isinstance(table, (str, bytes)):
        raise DSLExecutionError(
            "TABLE_REQUIRED",
            "A row-oriented FinQA table is required for table operations.",
            step_index=step_index,
        )
    try:
        rows = list(table)
    except TypeError as exc:
        raise DSLExecutionError(
            "INVALID_TABLE",
            "Table must be a sequence of row sequences.",
            step_index=step_index,
        ) from exc

    label = _decode_row_label(row_token, step_index=step_index)
    wanted = _normalize_label(label)
    matches: list[Sequence[Any]] = []
    for row in rows:
        if isinstance(row, (str, bytes)):
            raise DSLExecutionError(
                "INVALID_TABLE",
                "Every table row must be a sequence of cells.",
                step_index=step_index,
            )
        try:
            if len(row) and _normalize_label(row[0]) == wanted:
                matches.append(row)
        except (TypeError, IndexError) as exc:
            raise DSLExecutionError(
                "INVALID_TABLE",
                "Every table row must be an indexable cell sequence.",
                step_index=step_index,
            ) from exc

    if not matches:
        raise DSLExecutionError(
            "TABLE_ROW_NOT_FOUND",
            f"Table row {label!r} was not found.",
            step_index=step_index,
            token=row_token,
        )
    if len(matches) > 1:
        raise DSLExecutionError(
            "TABLE_ROW_AMBIGUOUS",
            f"Table contains more than one row named {label!r}.",
            step_index=step_index,
            token=row_token,
        )

    values: list[float] = []
    for column_index, cell in enumerate(matches[0][1:], start=1):
        try:
            value = _parse_table_cell(cell)
        except ValueError as exc:
            raise DSLExecutionError(
                "INVALID_TABLE_CELL",
                f"Cell {column_index} of row {label!r} is not a supported FinQA number.",
                step_index=step_index,
                token=str(cell),
            ) from exc
        if value is not None:
            values.append(value)

    if not values:
        raise DSLExecutionError(
            "EMPTY_TABLE_ROW",
            f"Table row {label!r} has no numeric cells to aggregate.",
            step_index=step_index,
            token=row_token,
        )
    return label, tuple(values)


def _resolve_numeric_operand(
    token: str, values: Sequence[float | str], *, step_index: int
) -> float:
    reference = _REFERENCE_RE.fullmatch(token)
    if reference is not None:
        referenced_index = int(reference.group(1))
        # Static validation already prevents this, but retain the runtime guard
        # so future callers cannot accidentally bypass fail-closed behavior.
        if referenced_index >= len(values):
            raise DSLExecutionError(
                "INVALID_REFERENCE",
                f"Reference {token!r} has no computed value.",
                step_index=step_index,
                token=token,
            )
        value = values[referenced_index]
        if isinstance(value, str):
            raise DSLExecutionError(
                "NON_NUMERIC_REFERENCE",
                f"Reference {token!r} points to a yes/no result.",
                step_index=step_index,
                token=token,
            )
        return value

    folded = token.casefold()
    if folded in FINQA_CONSTANTS:
        return FINQA_CONSTANTS[folded]
    try:
        return _parse_numeric_literal(token)
    except ValueError as exc:  # Static validation should make this unreachable.
        raise DSLExecutionError(
            "INVALID_OPERAND",
            f"Operand {token!r} is not numeric.",
            step_index=step_index,
            token=token,
        ) from exc


def _ensure_finite(value: Any, *, step_index: int) -> float:
    if isinstance(value, complex):
        raise DSLExecutionError(
            "INVALID_ARITHMETIC_RESULT",
            "Operation produced a complex result.",
            step_index=step_index,
        )
    try:
        numeric = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise DSLExecutionError(
            "INVALID_ARITHMETIC_RESULT",
            "Operation did not produce a finite number.",
            step_index=step_index,
        ) from exc
    if not math.isfinite(numeric):
        raise DSLExecutionError(
            "NON_FINITE_RESULT",
            "Operation produced a non-finite number.",
            step_index=step_index,
        )
    return numeric


def execute_program(
    program: str,
    table: Sequence[Sequence[Any]] | None = None,
) -> ExecutionResult:
    """Execute a FinQA program and always return a structured result.

    No malformed input is coerced to zero, and no partially computed value is
    returned as the answer after an error.
    """

    raw_program = program.strip() if isinstance(program, str) else None
    try:
        parsed_steps = parse_program(program)
    except DSLParseError as exc:
        return ExecutionResult(
            ok=False,
            value=None,
            error=exc.detail,
            program=raw_program,
            steps=(),
        )

    canonical_program = _canonicalize_steps(parsed_steps)
    values: list[float | str] = []
    trace: list[ExecutionStep] = []

    try:
        for step in parsed_steps:
            left_token, right_token = step.arguments
            if step.operation in TABLE_OPERATIONS:
                _label, row_values = _table_row_values(table, left_token, step_index=step.index)
                if step.operation == "table_max":
                    result: float | str = max(row_values)
                elif step.operation == "table_min":
                    result = min(row_values)
                elif step.operation == "table_sum":
                    result = math.fsum(row_values)
                else:
                    result = math.fsum(row_values) / len(row_values)
                result = _ensure_finite(result, step_index=step.index)
                resolved_arguments: tuple[Any, Any] = (row_values, None)
            else:
                left = _resolve_numeric_operand(left_token, values, step_index=step.index)
                right = _resolve_numeric_operand(right_token, values, step_index=step.index)
                resolved_arguments = (left, right)
                if step.operation == "add":
                    result = _ensure_finite(left + right, step_index=step.index)
                elif step.operation == "subtract":
                    result = _ensure_finite(left - right, step_index=step.index)
                elif step.operation == "multiply":
                    result = _ensure_finite(left * right, step_index=step.index)
                elif step.operation == "divide":
                    if right == 0.0:
                        raise DSLExecutionError(
                            "DIVISION_BY_ZERO",
                            "Division by zero is undefined.",
                            step_index=step.index,
                            token=right_token,
                        )
                    result = _ensure_finite(left / right, step_index=step.index)
                elif step.operation == "greater":
                    result = "yes" if left > right else "no"
                else:  # exp
                    try:
                        powered = left**right
                    except (OverflowError, ValueError, ZeroDivisionError) as exc:
                        raise DSLExecutionError(
                            "INVALID_EXPONENTIATION",
                            "Exponentiation is undefined or outside the finite range.",
                            step_index=step.index,
                        ) from exc
                    result = _ensure_finite(powered, step_index=step.index)

            values.append(result)
            trace.append(
                ExecutionStep(
                    index=step.index,
                    operation=step.operation,
                    arguments=step.arguments,
                    resolved_arguments=resolved_arguments,
                    value=result,
                )
            )
    except DSLExecutionError as exc:
        return ExecutionResult(
            ok=False,
            value=None,
            error=exc.detail,
            program=canonical_program,
            steps=tuple(trace),
        )

    return ExecutionResult(
        ok=True,
        value=values[-1],
        error=None,
        program=canonical_program,
        steps=tuple(trace),
    )


def _program_candidate_at(text: str, start: int) -> tuple[str, int] | None:
    """Return a maximal contiguous DSL sequence beginning at ``start``."""

    position = start
    end = start
    while position < len(text):
        operation_match = _IDENTIFIER_RE.match(text, position)
        if operation_match is None:
            return None
        operation = operation_match.group(0).casefold()
        if operation not in SUPPORTED_OPERATIONS:
            return None
        cursor = operation_match.end()
        while cursor < len(text) and text[cursor].isspace():
            cursor += 1
        if cursor >= len(text) or text[cursor] != "(":
            return None
        try:
            closing = _find_closing_parenthesis(text, cursor, step_index=0)
        except DSLParseError:
            # Preserve a visibly attempted program so execute_program can
            # report the real syntax error instead of extraction hiding it.
            return text[start:].strip(), len(text)
        end = closing + 1
        cursor = end
        while cursor < len(text) and text[cursor].isspace():
            cursor += 1
        if cursor >= len(text) or text[cursor] != ",":
            break
        next_start = cursor + 1
        while next_start < len(text) and text[next_start].isspace():
            next_start += 1
        next_operation = _IDENTIFIER_RE.match(text, next_start)
        if next_operation is None or next_operation.group(0).casefold() not in SUPPORTED_OPERATIONS:
            break
        after_identifier = next_operation.end()
        while after_identifier < len(text) and text[after_identifier].isspace():
            after_identifier += 1
        if after_identifier >= len(text) or text[after_identifier] != "(":
            break
        position = next_start
        end = cursor + 1
    return text[start:end].strip(), end


def _candidates_from_text(text: str) -> list[str]:
    candidates: list[str] = []
    cursor = 0
    while True:
        match = _DSL_START_RE.search(text, cursor)
        if match is None:
            break
        candidate = _program_candidate_at(text, match.start())
        if candidate is None:
            cursor = match.end()
            continue
        value, end = candidate
        if value:
            candidates.append(value)
        cursor = max(end, match.end())
    return candidates


def _program_from_json_value(value: Any) -> str | None:
    if not isinstance(value, Mapping):
        return None
    for key, program in value.items():
        if str(key).casefold() != "program":
            continue
        if isinstance(program, str) and program.strip():
            return program.strip()
        if isinstance(program, Sequence) and not isinstance(program, (str, bytes)):
            parts = [part.strip() for part in program if isinstance(part, str) and part.strip()]
            if parts:
                return ", ".join(parts)
    return None


def _decode_json_program(text: str) -> str | None:
    try:
        decoded = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        decoded = None
    direct = _program_from_json_value(decoded)
    if direct is not None:
        return direct

    # Also support an otherwise prose response containing a JSON program field.
    matches = list(re.finditer(r'"program"\s*:\s*("(?:\\.|[^"\\])*")', text, re.IGNORECASE))
    for match in reversed(matches):
        try:
            value = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def extract_program(text: Any) -> str | None:
    """Extract a FinQA program from fenced, plain, or JSON model output.

    The last fenced/labeled/raw candidate is preferred, matching the common
    model behavior of emitting a worked example before its final answer.
    Extraction does not execute or repair the candidate.
    """

    mapping_program = _program_from_json_value(text)
    if mapping_program is not None:
        return mapping_program
    if not isinstance(text, str) or not text.strip():
        return None

    clean = re.sub(r"<think\b[^>]*>.*?</think>", "", text, flags=re.IGNORECASE | re.DOTALL)
    blocks = _FENCED_BLOCK_RE.findall(clean)
    for block in reversed(blocks):
        json_program = _decode_json_program(block.strip())
        if json_program is not None:
            return json_program
        labeled = list(re.finditer(r"\bprogram\s*:\s*", block, re.IGNORECASE))
        for label in reversed(labeled):
            candidates = _candidates_from_text(block[label.end() :])
            if candidates:
                return candidates[0]
        candidates = _candidates_from_text(block)
        if candidates:
            return candidates[-1]

    json_program = _decode_json_program(clean.strip())
    if json_program is not None:
        return json_program

    labels = list(re.finditer(r"\bprogram\s*:\s*", clean, re.IGNORECASE))
    for label in reversed(labels):
        candidates = _candidates_from_text(clean[label.end() :])
        if candidates:
            return candidates[0]

    candidates = _candidates_from_text(clean)
    return candidates[-1] if candidates else None


def _legacy_number_text(text: str) -> str:
    try:
        value = float(text.replace(",", "").strip())
    except (TypeError, ValueError):
        return text
    if value == int(value):
        return str(int(value))
    return f"{value:.10f}".rstrip("0").rstrip(".")


def normalize_program_legacy(program: str | None) -> str:
    """Reproduce the notebook-era permissive PA normalization.

    This function is intentionally *not* used for execution or strict
    canonicalization.  It strips percent signs without dividing by 100,
    reorders commutative operands, and renumbers references by first appearance
    for compatibility with already-published notebook artifacts.
    """

    if not program:
        return ""
    normalized = re.sub(r"\s+", "", str(program).casefold())

    def replace_constant(match: re.Match[str]) -> str:
        name = match.group(0).casefold()
        if name not in FINQA_CONSTANTS:
            return name
        return _legacy_number_text(str(FINQA_CONSTANTS[name]))

    normalized = re.sub(
        r"\bconst_[A-Za-z0-9_]+\b", replace_constant, normalized, flags=re.IGNORECASE
    )
    normalized = re.sub(r"(\d)%", r"\1", normalized)
    normalized = re.sub(r"(?<![\w.])\.(\d)", r"0.\1", normalized)
    normalized = re.sub(
        r"(?<!#)\b\d+(?:\.\d+)?",
        lambda match: _legacy_number_text(match.group(0)),
        normalized,
    )
    normalized = re.sub(
        r"add\(([^,]+),([^)]+)\)",
        lambda match: "add(" + ",".join(sorted(match.groups())) + ")",
        normalized,
    )
    normalized = re.sub(
        r"multiply\(([^,]+),([^)]+)\)",
        lambda match: "multiply(" + ",".join(sorted(match.groups())) + ")",
        normalized,
    )

    references: list[str] = []

    def renumber_reference(match: re.Match[str]) -> str:
        reference = match.group(0)
        if reference not in references:
            references.append(reference)
        return f"#{references.index(reference)}"

    return re.sub(r"#\d+", renumber_reference, normalized)


__all__ = [
    "ARITHMETIC_OPERATIONS",
    "DSLExecutionError",
    "DSLError",
    "DSLParseError",
    "ExecutionResult",
    "ExecutionStep",
    "FINQA_CONSTANTS",
    "ProgramStep",
    "SUPPORTED_OPERATIONS",
    "TABLE_OPERATIONS",
    "canonicalize_program_strict",
    "execute_program",
    "extract_program",
    "normalize_program_legacy",
    "parse_program",
]
