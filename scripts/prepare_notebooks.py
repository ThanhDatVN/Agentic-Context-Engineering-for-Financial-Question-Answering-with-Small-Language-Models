"""Strip transient notebook state and add a stable introductory cell.

This script intentionally uses only the Python standard library so it can run in
CI before Jupyter is installed.
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

INTRO_MARKER = "ace-finqa-notebook-intro"


def _intro_for(path: Path) -> dict[str, Any]:
    if "baseline" in path.stem:
        title = "Qwen3-8B oracle-context baseline"
        purpose = (
            "Runs the Qwen3-8B FS-9 baseline on FinQA and writes resumable prediction artifacts."
        )
    else:
        title = "ACE-FinQA playbook experiment"
        purpose = "Builds and evaluates an adaptive ACE playbook for Qwen3-8B on FinQA."

    source = [
        f'<a id="{INTRO_MARKER}"></a>\n',
        f"# {title}\n",
        "\n",
        f"{purpose}\n",
        "\n",
        "> **Status:** Colab-first experiment. Read "
        "[`docs/reproducibility.md`](../docs/reproducibility.md) before running. "
        "Notebook metrics are run diagnostics. The canonical project result is "
        "published in [`results/report.md`](../results/report.md) from the thesis record.\n",
        "\n",
        "Run cells from top to bottom in a fresh runtime. Never commit outputs, "
        "widget state, credentials, or downloaded weights.\n",
    ]
    return {
        "cell_type": "markdown",
        "metadata": {"tags": ["documentation"]},
        "source": source,
    }


def cleaned_notebook(notebook: dict[str, Any], path: Path) -> dict[str, Any]:
    cleaned = copy.deepcopy(notebook)
    metadata = cleaned.setdefault("metadata", {})
    metadata.pop("widgets", None)

    cells = cleaned.setdefault("cells", [])
    for cell in cells:
        if cell.get("cell_type") == "code":
            cell["execution_count"] = None
            cell["outputs"] = []
        cell_metadata = cell.setdefault("metadata", {})
        cell_metadata.pop("execution", None)
        cell_metadata.pop("collapsed", None)
        cell_metadata.pop("scrolled", None)
        cell_metadata.pop("outputId", None)
        cell_metadata.pop("colab", None)

    intro_index = next(
        (
            index
            for index, cell in enumerate(cells)
            if cell.get("cell_type") == "markdown"
            and INTRO_MARKER in "".join(cell.get("source", []))
        ),
        None,
    )
    if intro_index is None:
        cells.insert(0, _intro_for(path))
    else:
        cells[intro_index] = _intro_for(path)

    return cleaned


def process(path: Path, check: bool) -> bool:
    original = json.loads(path.read_text(encoding="utf-8"))
    cleaned = cleaned_notebook(original, path)
    changed = original != cleaned

    if changed and not check:
        rendered = json.dumps(cleaned, ensure_ascii=False, indent=1) + "\n"
        path.write_text(rendered, encoding="utf-8", newline="\n")
    return changed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="report dirty notebooks without modifying them",
    )
    parser.add_argument("paths", nargs="+", type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    dirty: list[Path] = []
    for path in args.paths:
        if process(path, check=args.check):
            dirty.append(path)

    if args.check and dirty:
        print("Notebook outputs or transient metadata must be cleaned:")
        for path in dirty:
            print(f"  - {path}")
        return 1

    if not args.check:
        for path in dirty:
            print(f"Cleaned {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
