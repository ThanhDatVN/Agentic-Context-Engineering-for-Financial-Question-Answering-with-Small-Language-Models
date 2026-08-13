# Thesis-reported figures

These SVG charts are generated from the Chapter 4 CSV transcriptions and contain no independently entered values. They visualize what the thesis reports; they are not the audited primary result. Read [`../audit.md`](../audit.md) before citing them.

- [`model_comparison.svg`](model_comparison.svg) — Table 4.4 in thesis order;
- [`complexity_gain.svg`](complexity_gain.svg) — Table 4.5 on the FinQA dev split;
- [`ablation_effects.svg`](ablation_effects.svg) — Table 4.7 deltas from full ACE-FinQA.

Regenerate and verify them with:

```bash
python scripts/generate_result_figures.py
python scripts/generate_result_figures.py --check
```

Notebook-created figures are run diagnostics and are not part of the audited record.
