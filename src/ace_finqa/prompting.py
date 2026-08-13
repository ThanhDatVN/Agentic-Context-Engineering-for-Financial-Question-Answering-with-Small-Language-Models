"""Explicit FinQA context and prompt construction.

The notebooks used annotated ``gold_inds`` implicitly. This module makes that
choice visible through :class:`ContextMode` so oracle and full-context results
cannot be confused accidentally.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any


class ContextBuildError(ValueError):
    """Raised when the requested context mode cannot be built safely."""


class ContextMode(str, Enum):
    """Evidence supplied to the model."""

    ORACLE = "oracle"
    FULL = "full"


@dataclass(frozen=True)
class PromptSpec:
    """Tokenizer-independent prompt configuration."""

    system_prompt: str
    output_instruction: str = "Write the program in a ```plaintext block."
    context_mode: ContextMode = ContextMode.ORACLE


DEFAULT_SYSTEM_PROMPT = (
    "You are a financial analyst. Given evidence from an SEC filing, write a flat FinQA "
    "DSL program using add, subtract, multiply, divide, greater, exp, or table aggregates. "
    "Use #0, #1, ... only for results from earlier operations. Return decimal values for "
    "percentages and output only the requested program."
)


def _clean_cell(value: Any) -> str:
    return str(value).replace("$", "").replace(",", "").strip()


def table_to_markdown(table: Sequence[Sequence[Any]]) -> str:
    """Render a rectangular or ragged FinQA table without pandas."""

    if not table:
        return ""
    width = max((len(row) for row in table), default=0)
    if width == 0:
        return ""
    rows = [[_clean_cell(cell) for cell in row] + [""] * (width - len(row)) for row in table]
    header = rows[0]
    separator = ["---"] * width
    return "\n".join(" | ".join(row) for row in [header, separator, *rows[1:]])


def _full_context(sample: Mapping[str, Any]) -> str:
    pre = " ".join(str(value) for value in sample.get("pre_text", [])).strip()
    post = " ".join(str(value) for value in sample.get("post_text", [])).strip()
    text = " ".join(part for part in (pre, post) if part).strip()
    table = table_to_markdown(sample.get("table", []))
    parts = []
    if text:
        parts.append(f"Text: {text}")
    if table:
        parts.append(f"Table:\n{table}")
    if not parts:
        raise ContextBuildError("Sample has neither textual nor tabular context")
    return "\n".join(parts)


def _oracle_context(sample: Mapping[str, Any]) -> str:
    qa = sample.get("qa")
    if not isinstance(qa, Mapping):
        raise ContextBuildError("Sample is missing qa")
    gold_inds = qa.get("gold_inds")
    if not isinstance(gold_inds, Mapping) or not gold_inds:
        raise ContextBuildError("Oracle context requires non-empty qa.gold_inds")

    text_facts: list[str] = []
    table_indices: list[int] = []
    for key, value in gold_inds.items():
        if str(key).startswith("text_"):
            text_facts.append(str(value).strip())
        elif str(key).startswith("table_"):
            try:
                table_indices.append(int(str(key).split("_", 1)[1]))
            except ValueError as exc:
                raise ContextBuildError(f"Invalid oracle table index: {key}") from exc

    parts: list[str] = []
    if text_facts:
        parts.append("Text: " + " ".join(fact for fact in text_facts if fact))
    if table_indices:
        table = sample.get("table")
        if not isinstance(table, list) or not table:
            raise ContextBuildError("Oracle indices reference a missing table")
        rows = [table[0]]
        for index in sorted(set(table_indices)):
            if not 0 < index < len(table):
                raise ContextBuildError(f"Oracle table index out of range: {index}")
            rows.append(table[index])
        parts.append(f"Table:\n{table_to_markdown(rows)}")
    if not parts:
        raise ContextBuildError("qa.gold_inds contains no usable text or table evidence")
    return "\n".join(parts)


def build_context(sample: Mapping[str, Any], mode: ContextMode | str) -> str:
    """Build evidence in an explicitly selected mode."""

    try:
        selected = mode if isinstance(mode, ContextMode) else ContextMode(mode)
    except ValueError as exc:
        raise ContextBuildError(f"Unsupported context mode: {mode}") from exc
    return _oracle_context(sample) if selected is ContextMode.ORACLE else _full_context(sample)


def build_user_prompt(
    sample: Mapping[str, Any],
    *,
    context_mode: ContextMode | str,
    output_instruction: str = "Write the program in a ```plaintext block.",
    playbook: str | None = None,
    few_shot_examples: Sequence[Mapping[str, Any]] | None = None,
) -> str:
    """Build a plain user message without a model-specific chat template."""

    qa = sample.get("qa")
    if not isinstance(qa, Mapping) or not isinstance(qa.get("question"), str):
        raise ContextBuildError("Sample is missing qa.question")
    sections = [f"Context:\n{build_context(sample, context_mode)}"]
    if playbook and playbook.strip():
        sections.append("Learned strategies (secondary hints):\n" + playbook.strip())
    if few_shot_examples:
        rendered: list[str] = []
        for number, example in enumerate(few_shot_examples, 1):
            example_qa = example.get("qa")
            if not isinstance(example_qa, Mapping):
                raise ContextBuildError("Few-shot example is missing qa")
            question = example_qa.get("question")
            program = example_qa.get("program")
            if not isinstance(question, str) or not isinstance(program, str):
                raise ContextBuildError("Few-shot example requires question and program")
            rendered.append(f"Example {number}: {question}\n```plaintext\nprogram: {program}\n```")
        sections.append("Similar solved examples:\n" + "\n\n".join(rendered))
    sections.append(f"Question: {qa['question']}\n\n{output_instruction}")
    return "\n\n".join(sections)


def build_messages(
    sample: Mapping[str, Any],
    spec: PromptSpec,
    *,
    playbook: str | None = None,
    few_shot_examples: Sequence[Mapping[str, Any]] | None = None,
) -> list[dict[str, str]]:
    """Return generic chat messages for any downstream inference backend."""

    return [
        {"role": "system", "content": spec.system_prompt},
        {
            "role": "user",
            "content": build_user_prompt(
                sample,
                context_mode=spec.context_mode,
                output_instruction=spec.output_instruction,
                playbook=playbook,
                few_shot_examples=few_shot_examples,
            ),
        },
    ]
