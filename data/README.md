# FinQA data snapshot

This directory contains the public FinQA split files used by the historical notebooks.

| File | Examples | SHA-256 | Purpose |
|---|---:|---|---|
| [`finqa/train.json`](finqa/train.json) | 6,251 | `49f237eb9779b569473b26b08048867d04635a7cc39ad6a7a5664c55bb428db6` | Playbook training/source examples |
| [`finqa/dev.json`](finqa/dev.json) | 883 | `a847fb7e0d61a3125a1e2909852df6b89f1ee64d2c5ff1bf689e332214deee51` | Selection and development evaluation |
| [`finqa/test.json`](finqa/test.json) | 1,147 | `831dbfb2e785dbc227f895ce3f24046433467aec67b09db2bd6ac7692a8a30dc` | Retained test evaluation |

## Provenance and terms

FinQA was introduced by Chen et al. in *FinQA: A Dataset of Numerical Reasoning over Financial Data* (EMNLP 2021). The authoritative project is the [official FinQA repository](https://github.com/czyssrs/FinQA), which publishes its data and code under the MIT License. These snapshots remain third-party material; the ACE-FinQA repository license does not replace the upstream license or citation requirement.

The original commit/hash used when these copies were first added was not recorded. Treat the files as a convenience snapshot and compare them with an immutable upstream release before a publication rerun.

## Schema used by this project

Each record includes document text, a table, an identifier, and a `qa` object. The main fields used here are:

- `pre_text`, `post_text`, and `table`;
- `id`;
- `qa.question`;
- `qa.program` and `qa.exe_ans`;
- `qa.gold_inds` for annotated supporting evidence.

The notebooks construct context from `gold_inds`. Any metric produced this way must be labeled **oracle-context**. It does not measure retrieval.

## Validate locally

```bash
ace-finqa data-summary --data-dir data/finqa
ace-finqa verify-repo --data-dir data/finqa --results-dir results
```

Do not place private reports or newly downloaded datasets in this tracked directory. Use an ignored local path and record its checksum in the run manifest.

## Citation

```bibtex
@inproceedings{chen-etal-2021-finqa,
  title = {{FinQA}: A Dataset of Numerical Reasoning over Financial Data},
  author = {Chen, Zhiyu and Chen, Wenhu and Smiley, Charese and Shah, Sameena and
            Borova, Iana and Langdon, Dylan and Moussa, Reema and Beane, Matt and
            Huang, Ting-Hao and Routledge, Bryan and Wang, William Yang},
  booktitle = {Proceedings of EMNLP},
  year = {2021}
}
```
