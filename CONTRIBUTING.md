# Contributing

Thank you for improving ACE-FinQA. Changes should keep the result audit reproducible, make evaluation semantics explicit, preserve thesis transcriptions without treating them as verified, and separate GPU/API experiments from CPU validation.

The repository is currently All Rights Reserved. This guide does not grant
permission to copy, modify, or redistribute its original materials. Contact the
copyright holder for written authorization before preparing a contribution;
authorized contributions may then follow the workflow below.

## Development setup

Use Python 3.10 or newer:

```bash
python -m venv .venv
source .venv/bin/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

Run the local quality gates before opening a pull request:

```bash
ruff check src tests scripts
ruff format --check src tests scripts
python -m unittest discover -s tests -v
python scripts/refactor_notebooks.py --check notebooks/01_qwen3_baseline.ipynb notebooks/02_ace_finqa.ipynb
python scripts/prepare_notebooks.py --check notebooks/01_qwen3_baseline.ipynb notebooks/02_ace_finqa.ipynb
python scripts/check_consistency.py
python scripts/audit_historical_results.py  # requires full Git history
python scripts/generate_result_figures.py --check
ace-finqa verify-repo --data-dir data/finqa --results-dir results
```

## Research changes

- Treat `results/` as the reviewed audit record. Write new run artifacts to `outputs/` and replace audited values only after explicit review of raw counts, metric semantics, and provenance.
- Record the Git commit, configuration, seeds, dataset checksums, model revision, dependency versions, hardware, timestamps, and metric implementation for every new run.
- Name the context mode explicitly (`oracle`, `full`, or `retrieved`). Results that use FinQA `gold_inds` must be described as oracle-context results.
- Distinguish API-assisted training from API-free inference.
- Do not compare metrics produced by different evaluators without a visible qualification.

## Notebooks

Notebooks are experiment interfaces, not the canonical implementation. Reusable logic belongs under `src/ace_finqa/`. Before committing a notebook, strip execution outputs and widget state:

```bash
python scripts/prepare_notebooks.py notebooks/01_qwen3_baseline.ipynb notebooks/02_ace_finqa.ipynb
```

## Data and secrets

Do not commit API keys, `.env` files, model weights, checkpoints, private reports, or new third-party datasets without a license and provenance review. The bundled FinQA snapshot is governed by its upstream terms; see `data/README.md` and `THIRD_PARTY_NOTICES.md`.
