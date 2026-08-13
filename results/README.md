# Results

This directory separates audited results from values transcribed from the thesis:

- [`audit.md`](audit.md) — evidence-backed audit and thesis errata;
- [`report.md`](report.md) — concise audited and thesis-reported views;
- [`manifest.json`](manifest.json) — raw counts, metric profiles, source hashes, and known discrepancies;
- [`tables/`](tables/) — audited results plus transcriptions of the Chapter 4 tables;
- [`figures/`](figures/) — deterministic SVG charts of thesis-reported tables.

The retained historical test artifact supports **67.39% execution accuracy** and **61.90% program accuracy** for ACE-FinQA under its legacy notebook metric profile. The current `strict-v1` evaluator recomputes the same predictions as **67.74% / 59.90%**. The thesis's **68.06% / 61.90%** pair is preserved as a transcription but is not raw-artifact verified.

New experiment outputs must be written to `outputs/` or external storage. The detailed discussion and evaluation scope are available in [`docs/results.md`](../docs/results.md).
