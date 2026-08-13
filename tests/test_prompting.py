from __future__ import annotations

import unittest

from ace_finqa.prompting import (
    ContextBuildError,
    ContextMode,
    PromptSpec,
    build_context,
    build_messages,
    build_user_prompt,
    table_to_markdown,
)


def fixture() -> dict:
    return {
        "pre_text": ["Ignore this unrelated sentence.", "Revenue discussion."],
        "post_text": ["Post text."],
        "table": [
            ["", "2020", "2021"],
            ["revenue", "$ 100", "$ 120"],
            ["cost", "$ 70", "$ 80"],
        ],
        "qa": {
            "question": "What was the revenue change?",
            "program": "subtract(120, 100)",
            "exe_ans": 20,
            "gold_inds": {"text_1": "Revenue discussion.", "table_1": "revenue"},
        },
    }


class PromptingTests(unittest.TestCase):
    def test_oracle_context_contains_only_annotated_evidence(self) -> None:
        context = build_context(fixture(), ContextMode.ORACLE)
        self.assertIn("Revenue discussion.", context)
        self.assertIn("revenue | 100 | 120", context)
        self.assertNotIn("cost |", context)
        self.assertNotIn("Ignore this", context)

    def test_full_context_contains_all_evidence(self) -> None:
        context = build_context(fixture(), "full")
        self.assertIn("Ignore this unrelated sentence.", context)
        self.assertIn("cost | 70 | 80", context)

    def test_oracle_mode_does_not_silently_fallback(self) -> None:
        value = fixture()
        value["qa"]["gold_inds"] = {}
        with self.assertRaises(ContextBuildError):
            build_context(value, ContextMode.ORACLE)

    def test_invalid_oracle_index_fails(self) -> None:
        value = fixture()
        value["qa"]["gold_inds"] = {"table_99": "missing"}
        with self.assertRaisesRegex(ContextBuildError, "out of range"):
            build_context(value, ContextMode.ORACLE)

    def test_ragged_table_is_rendered(self) -> None:
        rendered = table_to_markdown([["a", "b"], ["1"]])
        self.assertEqual(rendered.splitlines()[-1], "1 | ")

    def test_prompt_and_messages_are_backend_independent(self) -> None:
        prompt = build_user_prompt(
            fixture(),
            context_mode="oracle",
            playbook="- Prefer subtract(new, old).",
            few_shot_examples=[fixture()],
        )
        self.assertIn("Learned strategies", prompt)
        self.assertIn("Example 1", prompt)
        messages = build_messages(
            fixture(), PromptSpec(system_prompt="system", context_mode=ContextMode.FULL)
        )
        self.assertEqual([message["role"] for message in messages], ["system", "user"])
        self.assertEqual(messages[0]["content"], "system")


if __name__ == "__main__":
    unittest.main()
