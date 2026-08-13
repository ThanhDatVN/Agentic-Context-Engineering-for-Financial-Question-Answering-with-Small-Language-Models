# Reproducibility

## Reproducibility levels

This repository separates three different goals:

1. **CPU validation** checks data shape, the fail-closed DSL implementation, prediction schemas, notebook cleanliness, and consistency of the thesis result record.
2. **Result inspection** validates raw-count arithmetic, metric-profile separation, source hashes, known thesis discrepancies, and faithful transcription of the thesis tables.
3. **GPU experiment rerun** executes the Colab notebooks. Exact reproduction additionally requires immutable model revisions, a complete dependency lock, prompt/config hashes, and full environment metadata.

## CPU validation

CI installs the exact development environment from `uv.lock`. Reproduce that path locally with:

```bash
uv sync --locked --extra dev
```

Alternatively, create a conventional virtual environment:

```bash
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

Then run the validation suite from the activated environment:

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

This path is network-free after installation and requires neither a GPU nor an API key.

## Colab/GPU prerequisites

- Linux CUDA runtime and an NVIDIA GPU with enough memory for Qwen3-8B and vLLM;
- Google Colab/Drive for the current notebook path and checkpoint workflow;
- FinQA `train.json`, `dev.json`, and `test.json` under the configured data directory;
- network access for Python packages and model weights;
- an OpenAI API key in Colab Secrets for ACE training;
- the GPU dependency set in [`requirements/experiment.txt`](../requirements/experiment.txt).

The notebooks currently pin some high-risk compatibility packages but are not a complete lockfile. Review their installation cells before running. A T4/unknown GPU path may still require smaller batch, sequence, and model-loading settings.

The cleaned rerun profile uses seed 42, Qwen3-8B in 4-bit NF4, a 4,096-token context, nine prompt examples, generator temperature 0, GPT-4o mini reflection at temperature 0 with JSON output, one pass over a target of 600 stratified training examples, a fixed 100-example mini-dev set, and at most three Verify-Iterate rounds. Verification requires both EA and PA. The evaluator fails closed and compares FinQA answers after rounding to five decimal places. Training starts from an empty playbook with no warm start or manual editing.

This is not the exact observed historical run. Retained metadata records 2 completed epochs, a realized 594-example subset, 780 completed steps, GPT-4o reflection, at most 5 verification rounds, `verify_require_pa=false`, and an 8,192-token context; historical notebook output records BF16 loading. Both profiles are recorded in [`results/manifest.json`](../results/manifest.json); consult [`results/audit.md`](../results/audit.md) before attempting a reproduction.

[`.env.example`](../.env.example) is a variable inventory only; the project
does not auto-load `.env`. Export values into the process environment or use
Colab Secrets before running a notebook.

## Baseline notebook

1. Open [`01_qwen3_baseline.ipynb`](../notebooks/01_qwen3_baseline.ipynb) in a fresh Colab runtime.
2. Set `ACE_FINQA_DRIVE_BASE`, `ACE_FINQA_DATA_DIR`, `ACE_FINQA_OUTPUT_DIR`, and optionally `ACE_FINQA_EVAL_SPLIT` before the configuration cell if the defaults do not match your Drive.
3. Run all cells in order.
4. Write output to a new run directory under `outputs/` or external storage. Never overwrite `results/`.
5. Evaluate saved predictions with the repository CLI and the same thesis evaluation protocol before proposing a new publication record.

The baseline notebook separates train/dev/test paths and uses the thesis FS-9 prompt. Its inline metrics are run diagnostics; audited results under `results/` remain unchanged unless a new result is deliberately reviewed and published with raw counts and an explicit metric profile.

## ACE notebook

1. Open [`02_ace_finqa.ipynb`](../notebooks/02_ace_finqa.ipynb) in a fresh runtime.
2. Put `OPENAI_API_KEY` in Colab Secrets; do not paste it into a cell.
3. Review the configuration section. Effective values are consolidated there; there are no later override cells.
4. Use a new `RUN_NAME` and an empty output directory.
5. Run cells once, from top to bottom. Rerunning stateful training cells can mutate the in-memory playbook.
6. Preserve every run with a new manifest. Do not merge its chunks with an older run.

The ACE notebook defaults to an empty playbook and refuses ambiguous reuse of an existing run directory. Resume is an explicit recovery feature for interrupted runs and must not be used to warm-start a new experiment. A run from the cleaned notebook is a new rerun, not a continuation of or exact substitute for the historical run.

## Required manifest for a new result

Record at least:

- Git commit and dirty-worktree state;
- UTC start/end time and run identifier;
- all configuration values and a config hash;
- Python and dependency freeze;
- OS, GPU, driver, CUDA, CPU, RAM, and storage;
- dataset source, split counts, and SHA-256 checksums;
- model repository and immutable revision;
- API model/version, call count, token count, and cost where applicable;
- all random seeds and deterministic settings;
- prompt, cluster catalog, and initial/final playbook hashes;
- context mode (`oracle`, `full`, or `retrieved`);
- evaluator name/version and tolerance;
- raw counts as well as rates.

## Experiment environment

The notebooks target Python on Google Colab with PyTorch, vLLM, Transformers, Unsloth, sentence-transformers, and the OpenAI client. Treat the dependency list as an experiment bootstrap rather than a bit-for-bit lock. A publication rerun must record immutable model and package revisions, hardware, prompts, data hashes, seeds, and evaluator settings in its manifest.
