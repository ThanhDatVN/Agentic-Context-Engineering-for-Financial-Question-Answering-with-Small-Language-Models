# Thesis tables

The audit table contains count-backed test metrics. The remaining CSV files reproduce the quantitative tables from Chapter 4 of [`docs/thesis.pdf`](../../docs/thesis.pdf); their percentages and deltas are stored exactly as reported and inherit the discrepancies documented in [`../audit.md`](../audit.md).

| Source | File | Description |
|---|---|---|
| Audit A.1 | [`table_a_1_audited_test_results.csv`](table_a_1_audited_test_results.csv) | Historical and `strict-v1` test results with raw counts |
| 4.1 | [`table_4_1_qwen3_baseline_by_steps.csv`](table_4_1_qwen3_baseline_by_steps.csv) | Qwen3-8B baseline by program length |
| 4.2 | [`table_4_2_qwen3_baseline_by_operator.csv`](table_4_2_qwen3_baseline_by_operator.csv) | Qwen3-8B baseline EA by first operation |
| 4.3 | [`table_4_3_qwen3_baseline_error_classes.csv`](table_4_3_qwen3_baseline_error_classes.csv) | Qwen3-8B baseline error classes |
| 4.4 | [`table_4_4_model_comparison.csv`](table_4_4_model_comparison.csv) | Main model comparison |
| 4.5 | [`table_4_5_ace_gain_over_qwen3_by_steps.csv`](table_4_5_ace_gain_over_qwen3_by_steps.csv) | ACE gain over Qwen3-8B by program length |
| 4.6 | [`table_4_6_qwen3_ace_outcomes.csv`](table_4_6_qwen3_ace_outcomes.csv) | Qwen3-8B and ACE outcome distribution |
| 4.7 | [`table_4_7_ablation.csv`](table_4_7_ablation.csv) | Ablation study |
