# Experiment notebooks

The notebooks are clean, Colab-first experiment interfaces. Reusable CPU logic lives under `src/ace_finqa/` and is covered by tests.

Run in this order and always in a fresh runtime:

1. [`01_qwen3_baseline.ipynb`](01_qwen3_baseline.ipynb) for baseline inference and diagnostics.
2. [`02_ace_finqa.ipynb`](02_ace_finqa.ipynb) for ACE playbook training and final evaluation.

Before execution, read [`docs/reproducibility.md`](../docs/reproducibility.md). Both notebooks assume a CUDA/Linux/Colab environment and external model downloads. ACE training additionally requires an OpenAI API key stored in Colab Secrets. Their committed defaults define a cleaned rerun profile in [`results/manifest.json`](../results/manifest.json); they do not exactly match the retained historical run metadata documented in [`results/audit.md`](../results/audit.md).

Experiment logic is organized into named sections. Large cells are split at safe top-level boundaries, configuration has one visible source of truth, and revision-history comments are removed. Code cells are capped at 320 lines because a few stateful functions cannot be split safely without a larger package refactor.

Metrics produced inside a notebook are run diagnostics, not a second project result. The audited record is [`results/report.md`](../results/report.md). A new run may replace it only after preserving raw predictions and counts, declaring the metric profile, recording a complete manifest, and passing repository consistency checks.

Before committing any notebook change:

```bash
python scripts/refactor_notebooks.py notebooks/01_qwen3_baseline.ipynb notebooks/02_ace_finqa.ipynb
python scripts/prepare_notebooks.py notebooks/01_qwen3_baseline.ipynb notebooks/02_ace_finqa.ipynb
python scripts/check_consistency.py
python scripts/generate_result_figures.py --check
```
