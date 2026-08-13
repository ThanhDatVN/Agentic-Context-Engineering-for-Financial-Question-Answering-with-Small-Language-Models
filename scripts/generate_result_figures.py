"""Generate deterministic SVG figures from thesis-reported result tables."""

from __future__ import annotations

import argparse
import csv
import html
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TABLE_DIR = ROOT / "results" / "tables"
FIGURE_DIR = ROOT / "results" / "figures"

BLUE = "#2563eb"
PURPLE = "#7c3aed"
INK = "#172033"
MUTED = "#5f6b7a"
GRID = "#d9e0e8"
PAPER = "#ffffff"


def _attribute_value(value: object) -> str:
    if isinstance(value, float):
        return f"{value:.3f}".rstrip("0").rstrip(".")
    return str(value)


def _rows(name: str) -> list[dict[str, str]]:
    with (TABLE_DIR / name).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _text(x: float, y: float, value: str, **attrs: object) -> str:
    attributes = {"x": x, "y": y, "fill": INK, "font_size": 16, **attrs}
    rendered = " ".join(
        f'{key.replace("_", "-")}="{html.escape(_attribute_value(item))}"'
        for key, item in attributes.items()
    )
    return f"<text {rendered}>{html.escape(value)}</text>"


def _rect(x: float, y: float, width: float, height: float, fill: str, **attrs: object) -> str:
    attributes = {"x": x, "y": y, "width": width, "height": height, "fill": fill, **attrs}
    rendered = " ".join(
        f'{key.replace("_", "-")}="{html.escape(_attribute_value(item))}"'
        for key, item in attributes.items()
    )
    return f"<rect {rendered}/>"


def _line(x1: float, y1: float, x2: float, y2: float, **attrs: object) -> str:
    attributes = {"x1": x1, "y1": y1, "x2": x2, "y2": y2, **attrs}
    rendered = " ".join(
        f'{key.replace("_", "-")}="{html.escape(_attribute_value(item))}"'
        for key, item in attributes.items()
    )
    return f"<line {rendered}/>"


def _document(title: str, description: str, width: int, height: int, body: list[str]) -> str:
    content = "\n  ".join(body)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">\n'
        f'  <title id="title">{html.escape(title)}</title>\n'
        f'  <desc id="desc">{html.escape(description)}</desc>\n'
        "  <style>text{font-family:Inter,'Segoe UI',Arial,sans-serif}</style>\n"
        f"  {_rect(0, 0, width, height, PAPER)}\n"
        f"  {content}\n"
        "</svg>\n"
    )


def _model_comparison() -> str:
    rows = _rows("table_4_4_model_comparison.csv")
    width, height = 1120, 590
    left, right, top = 345, 1050, 155
    scale = (right - left) / 100
    body = [
        _text(56, 56, "Thesis-reported FinQA comparison", font_size=28, font_weight=700),
        _text(56, 88, "Table 4.4 transcription · see results/audit.md", fill=MUTED),
        _rect(760, 48, 18, 18, BLUE, rx=3),
        _text(787, 63, "Execution accuracy", font_size=14),
        _rect(930, 48, 18, 18, PURPLE, rx=3),
        _text(957, 63, "Program accuracy", font_size=14),
    ]
    for tick in range(0, 101, 20):
        x = left + tick * scale
        body.append(_line(x, 125, x, 535, stroke=GRID, stroke_width=1))
        body.append(_text(x, 555, f"{tick}%", text_anchor="middle", fill=MUTED, font_size=13))

    for index, row in enumerate(rows):
        y = top + index * 76
        method = row["method"]
        if method.startswith("Qwen3"):
            body.append(_rect(38, y - 26, 1030, 62, "#eff6ff", rx=8))
            role = "Project baseline"
        elif method == "ACE-FinQA":
            body.append(_rect(38, y - 26, 1030, 62, "#f5f3ff", rx=8))
            role = "Proposed method"
        else:
            role = "External reference"
        ea = float(row["execution_accuracy_pct"])
        pa = float(row["program_accuracy_pct"])
        body.extend(
            [
                _text(
                    56,
                    y,
                    method,
                    font_size=16,
                    font_weight=650 if role != "External reference" else 500,
                ),
                _text(56, y + 21, role, font_size=12, fill=MUTED),
                _rect(left, y - 18, ea * scale, 17, BLUE, rx=3),
                _rect(left, y + 5, pa * scale, 17, PURPLE, rx=3),
                _text(left + ea * scale + 8, y - 5, f"{ea:.2f}%", font_size=13, fill=INK),
                _text(left + pa * scale + 8, y + 19, f"{pa:.2f}%", font_size=13, fill=INK),
            ]
        )
    return _document(
        "Thesis-reported FinQA model comparison",
        "Transcription of Thesis Table 4.4. See results/audit.md for discrepancies "
        "and count-backed audited results.",
        width,
        height,
        body,
    )


def _complexity_gain() -> str:
    rows = _rows("table_4_5_ace_gain_over_qwen3_by_steps.csv")
    width, height = 1120, 620
    left, right, top, bottom = 115, 1040, 135, 510
    scale = (bottom - top) / 80
    group_width = (right - left) / len(rows)
    body = [
        _text(
            56,
            56,
            "Thesis-reported gain by program length",
            font_size=28,
            font_weight=700,
        ),
        _text(56, 88, "Table 4.5 transcription · see results/audit.md", fill=MUTED),
        _rect(760, 48, 18, 18, BLUE, rx=3),
        _text(787, 63, "Qwen3-8B", font_size=14),
        _rect(900, 48, 18, 18, PURPLE, rx=3),
        _text(927, 63, "ACE-FinQA", font_size=14),
    ]
    for tick in range(0, 81, 20):
        y = bottom - tick * scale
        body.append(_line(left, y, right, y, stroke=GRID, stroke_width=1))
        body.append(
            _text(left - 14, y + 5, f"{tick}%", text_anchor="end", fill=MUTED, font_size=13)
        )
    for index, row in enumerate(rows):
        center = left + group_width * (index + 0.5)
        qwen = float(row["qwen3_execution_accuracy_pct"])
        ace = float(row["ace_execution_accuracy_pct"])
        gain = float(row["gain_points"])
        body.extend(
            [
                _rect(center - 42, bottom - qwen * scale, 34, qwen * scale, BLUE, rx=3),
                _rect(center + 8, bottom - ace * scale, 34, ace * scale, PURPLE, rx=3),
                _text(
                    center,
                    bottom + 31,
                    row["gold_program_steps"],
                    text_anchor="middle",
                    font_weight=650,
                ),
                _text(
                    center,
                    bottom + 52,
                    f"n={row['examples']}",
                    text_anchor="middle",
                    fill=MUTED,
                    font_size=12,
                ),
                _text(
                    center,
                    min(bottom - ace * scale, bottom - qwen * scale) - 13,
                    f"+{gain:.2f}",
                    text_anchor="middle",
                    fill=PURPLE,
                    font_size=14,
                    font_weight=700,
                ),
            ]
        )
    body.append(
        _text(
            (left + right) / 2,
            598,
            "Gold-program steps",
            text_anchor="middle",
            fill=MUTED,
            font_size=14,
        )
    )
    return _document(
        "Thesis-reported ACE-FinQA gain by program length",
        "Transcription of Thesis Table 4.5. Displayed buckets do not aggregate to "
        "the thesis headline; see results/audit.md.",
        width,
        height,
        body,
    )


def _ablation() -> str:
    rows = _rows("table_4_7_ablation.csv")[1:]
    width, height = 1120, 700
    zero, scale, top = 940, 105, 150
    body = [
        _text(56, 56, "Thesis-reported ablation effects", font_size=28, font_weight=700),
        _text(56, 88, "Table 4.7 transcription · not independently recomputed", fill=MUTED),
        _rect(760, 48, 18, 18, BLUE, rx=3),
        _text(787, 63, "ΔEA", font_size=14),
        _rect(860, 48, 18, 18, PURPLE, rx=3),
        _text(887, 63, "ΔPA", font_size=14),
    ]
    for tick in range(-7, 2):
        x = zero + tick * scale
        body.append(_line(x, 125, x, 610, stroke=INK if tick == 0 else GRID, stroke_width=1))
        body.append(_text(x, 635, f"{tick:+d}", text_anchor="middle", fill=MUTED, font_size=12))
    for index, row in enumerate(rows):
        y = top + index * 68
        ea = float(row["delta_ea_points"])
        pa = float(row["delta_pa_points"])
        label = row["variant"].split(":", 1)[-1].strip()
        body.append(_text(56, y + 7, label, font_size=14))
        for offset, value, color in ((-11, ea, BLUE), (12, pa, PURPLE)):
            x = zero + min(value, 0) * scale
            width_value = abs(value) * scale
            body.append(_rect(x, y + offset - 7, width_value, 14, color, rx=3))
            label_x = zero + value * scale + (8 if value >= 0 else -8)
            body.append(
                _text(
                    label_x,
                    y + offset + 5,
                    f"{value:+.1f}",
                    text_anchor="start" if value >= 0 else "end",
                    fill=color,
                    font_size=12,
                    font_weight=700,
                )
            )
    body.append(
        _text(
            660,
            675,
            "Percentage-point change",
            text_anchor="middle",
            fill=MUTED,
            font_size=14,
        )
    )
    return _document(
        "Thesis-reported ACE-FinQA ablation effects",
        "Transcription of Thesis Table 4.7; per-example ablation artifacts were not "
        "retained for independent recomputation.",
        width,
        height,
        body,
    )


def generated_figures() -> dict[str, str]:
    return {
        "model_comparison.svg": _model_comparison(),
        "complexity_gain.svg": _complexity_gain(),
        "ablation_effects.svg": _ablation(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify generated figures without writing",
    )
    args = parser.parse_args()
    expected = generated_figures()
    stale = [
        name
        for name, content in expected.items()
        if not (FIGURE_DIR / name).is_file()
        or (FIGURE_DIR / name).read_text(encoding="utf-8") != content
    ]
    if args.check:
        if stale:
            print("Figures are missing or stale: " + ", ".join(stale))
            return 1
        print("Thesis-reported figures match their CSV transcriptions.")
        return 0
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    for name, content in expected.items():
        (FIGURE_DIR / name).write_text(content, encoding="utf-8", newline="\n")
    print(f"Generated {len(expected)} thesis figures in {FIGURE_DIR.relative_to(ROOT)}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
