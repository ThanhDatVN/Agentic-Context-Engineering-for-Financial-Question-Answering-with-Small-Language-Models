# ACE-FinQA results

**Task:** FinQA program synthesis with annotated evidence.
**Test result:** **68.06% EA / 61.90% PA** on the 1,147-example FinQA test split.

## Model comparison

| Method | EA | PA |
|---|---:|---:|
| Qwen3-8B Eng-Prompt (FS-9) | 59.55% | 52.66% |
| FinQANet (RoBERTa-large) | 61.24% | 58.86% |
| **ACE-FinQA** | **68.06%** | **61.90%** |
| FinQANet-Gold (oracle retriever) | 70.00% | 68.76% |
| Human Expert (CPA/MBA) | 91.16% | 87.49% |

ACE-FinQA gains **8.51 EA points** and **9.24 PA points** over the Qwen3-8B baseline, and **6.82 EA points** and **3.04 PA points** over FinQANet. FinQANet-Gold and the human reference use an oracle retriever and remain above the playbook result.

![FinQA model comparison](figures/model_comparison.svg)

## FinQA dev complexity analysis

| Gold-program steps | Examples | Qwen3-8B EA | ACE EA | Gain |
|---:|---:|---:|---:|---:|
| 1 | 522 | 65.97% | 70.69% | +4.72 |
| 2 | 289 | 64.81% | 70.93% | +6.12 |
| 3 | 43 | 32.56% | 48.84% | +16.28 |
| 4 | 14 | 21.43% | 35.71% | +14.28 |
| 5+ | 15 | 20.00% | 33.33% | +13.33 |

The gain grows with program length. The largest improvements fall on 3-step and longer programs, where the baseline degrades most. The 4-step and 5+-step buckets hold 14 and 15 examples, so those two rows carry wide confidence intervals.

![ACE-FinQA gain by program length on FinQA dev](figures/complexity_gain.svg)

## Ablation study

| Variant | EA | PA | ΔEA | ΔPA |
|---|---:|---:|---:|---:|
| Full ACE-FinQA | **68.06%** | **61.90%** | — | — |
| No cluster pipeline | 64.80% | 58.10% | -3.3 | -3.8 |
| No Verify-Iterate | 65.00% | 56.70% | -3.1 | -5.2 |
| Flat memory, no Tier 1/2 | 66.30% | 60.00% | -1.8 | -1.9 |
| Heuristic/harm instead of dev-EMA | 65.80% | 57.50% | -2.3 | -4.4 |
| Two-layer Quality Gate | 64.30% | 56.10% | -3.8 | -5.8 |
| No role-based retrieval | 66.50% | 59.70% | -1.6 | -2.2 |
| EA-only selection, no PA guard | 68.30% | 55.70% | +0.2 | -6.2 |

Removing any single component costs EA. The clearest case is EA-only selection: dropping the PA guard buys 0.2 EA points and loses 6.2 PA points, which is why checkpoint selection is guarded by both metrics.

![ACE-FinQA ablation effects](figures/ablation_effects.svg)

The complete Chapter 4 table set is documented in [`docs/results.md`](../docs/results.md). Raw counts, the source commit and blob hashes of the retained run artifacts, and the recorded run configuration are in [`manifest.json`](manifest.json).
