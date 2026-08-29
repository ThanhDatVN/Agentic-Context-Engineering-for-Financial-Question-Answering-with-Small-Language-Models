# Results

This directory holds the published result record:

- [`report.md`](report.md) — the Chapter 4 results, gains, and figures;
- [`manifest.json`](manifest.json) — raw counts, source hashes, and the recorded run configuration;
- [`tables/`](tables/) — machine-readable copies of the Chapter 4 tables;
- [`figures/`](figures/) — deterministic SVG charts of those tables.

ACE-FinQA reaches **68.06% execution accuracy** and **61.90% program accuracy** on the 1,147-example FinQA test split, against **59.55% / 52.66%** for the Qwen3-8B FS-9 baseline.

New experiment outputs must be written to `outputs/` or external storage. The detailed discussion and evaluation scope are available in [`docs/results.md`](../docs/results.md).
