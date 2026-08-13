# Result audit and thesis errata

This audit separates three things that must not be mixed: the values printed in the thesis, the metrics stored by the historical notebooks, and a recomputation with the repository's current strict evaluator. The audit was performed against the 1,147-record FinQA test snapshot and the retained Git objects in commit `084446bce6b7b02ff29dc1db6df2f6d32a062974`.

## Audited test results

| Metric profile | Method | EA count | EA | PA count | PA |
|---|---|---:|---:|---:|---:|
| Historical notebook | Qwen3-8B FS-9 | 683/1,147 | 59.55% | 604/1,147 | 52.66% |
| Historical notebook | ACE-FinQA | 773/1,147 | 67.39% | 710/1,147 | 61.90% |
| Current `strict-v1` | Qwen3-8B FS-9 | 724/1,147 | 63.12% | 642/1,147 | 55.97% |
| Current `strict-v1` | ACE-FinQA | 777/1,147 | 67.74% | 687/1,147 | 59.90% |

Within the historical notebook profile, ACE adds 90 EA-correct and 106 PA-correct predictions: **+7.85 EA points** and **+9.24 PA points** from raw counts. Within `strict-v1`, it adds 53 EA-correct and 45 PA-correct predictions: **+4.62 EA points** and **+3.92 PA points**. Cross-profile comparisons are invalid because execution, normalization, answer tolerance, and program canonicalization differ.

`strict-v1` is a repository regression profile, not a claim of bit-for-bit equivalence with the official FinQA evaluator. The historical raw predictions are not duplicated in the cleaned working tree; their commit, Git blob IDs, SHA-256 hashes, counts, and derived rates are recorded in [`manifest.json`](manifest.json). They remain inspectable through Git history.

## Thesis discrepancies

The PDF is preserved unchanged as the submitted source document. Its Chapter 4 tables are transcribed under [`tables/`](tables/) and the generated figures, but they are now explicitly labeled thesis-reported rather than independently verified.

- Table 4.4 calls **68.06% EA / 61.90% PA** a test result. The retained ACE test summary instead contains 773 EA-correct and 710 PA-correct predictions, which yield **67.39% / 61.90%**. With a denominator of 1,147, no integer EA count rounds to 68.06%.
- Table 4.6 contains 883 outcomes. Applying the thesis's own EA/PA outcome definitions yields **62.40% EA / 53.34% PA** for the baseline and **68.06% EA / 62.85% PA** for ACE. The ACE EA is therefore a dev-sized outcome result, while the 61.90% PA in Table 4.4 matches the retained test result.
- Weighting the displayed Table 4.5 dev buckets yields **62.48% baseline EA** and **68.52% ACE EA**, so those buckets do not aggregate to Table 4.4 either.
- The historical run metadata records 2 completed epochs, 594 samples in the realized stratified subset, GPT-4o reflection, at most 5 verification rounds, `verify_require_pa=false`, and an 8,192-token context; the historical notebook execution output records BF16 model loading. These differ from parts of the thesis narrative and from the cleaned rerun notebook defaults.

The defensible project claim is therefore the audited, profile-specific result above. Thesis-only values and ablations remain useful as a record of what the thesis reported, but they must not be presented as raw-artifact-verified results until an erratum or a complete rerun resolves the discrepancies.

The external FinQANet, FinQANet-Gold, and human-reference scores in Thesis Table 4.4 were separately checked against the [official FinQA paper](https://aclanthology.org/2021.emnlp-main.300/) and the [corrected upstream repository](https://github.com/czyssrs/FinQA). This confirmation applies only to those external rows.
