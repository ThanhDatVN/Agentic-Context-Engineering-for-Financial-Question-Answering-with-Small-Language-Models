# FinQA data snapshot

This directory contains the public FinQA split files used by the historical notebooks.

| File | Examples | SHA-256 | Purpose |
|---|---:|---|---|
| [`finqa/train.json`](finqa/train.json) | 6,251 | `9862301c1a28f78bfb59050203bf66b13719c4720cd18291a069331b21c63352` | Playbook training/source examples |
| [`finqa/dev.json`](finqa/dev.json) | 883 | `27cc6c57487bbaba73041f93dba831a39b1cabe999c2ec0ddebc6f1200ff85bd` | Selection and development evaluation |
| [`finqa/test.json`](finqa/test.json) | 1,147 | `37a6e6e198b7821dc080f079d43a4a7a9d3a7b562803b7e97875bf70cd61fb08` | Retained test evaluation |

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
