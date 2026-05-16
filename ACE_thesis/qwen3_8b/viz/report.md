# ACE-Fin Results — qwen3_8b (FULL_thesis)

**Generated:** 2026-05-12 02:59:25
**Method:** Cluster-aware ACE + Tier 1 promotion + Dev lift tracking

## Configuration

| Parameter | Value |
|-----------|-------|
| Model | `unsloth/Qwen3-8B` |
| Mode | R20_BARE |
| Train subset | 594 |
| Total steps | 780 |
| Epochs | 2/2 |
| Reflector | gpt-4o |
| TOP_K Retrieval | 7 |
| Duration | 225.2 min |

## Main Results

| Metric | Value |
|--------|-------|
| Baseline step 0 EA | 0.6784 |
| Best Dev EA (step 300) | **0.6976** |
| Best Dev PA (step 300) | **0.6297** |
| **Test EA** | **0.6739** |
| **Test PA** | **0.6190** |
| Test None rate | 0.0523 |
| Bullets at best | 3 |
| Tier 1 promoted | 3 |
| Cluster diversity | 3 clusters |

## Target Achievement

| Target | Threshold | Achieved | Status |
|--------|-----------|----------|--------|
| Test EA | ≥ 0.70 | 0.6739 | ❌ MISSED by 2.61pp |
| Test PA | ≥ 0.60 | 0.6190 | ✅ PASSED |

## Test EA by Complexity

| Steps | Total | Correct | EA |
|-------|-------|---------|-----|
| 1-step | 654 | 452 | 0.691 |
| 2-step | 409 | 285 | 0.697 |
| 3-step | 55 | 31 | 0.564 |
| 4-step | 10 | 3 | 0.300 |
| 5-step | 19 | 2 | 0.105 |

## Training Failure Diagnosis

| Diagnosis | Count | % |
|-----------|-------|---|
| `missed_step` | 146 | 41.4% |
| `magnitude_error` | 63 | 17.8% |
| `wrong_direct_value` | 59 | 16.7% |
| `extra_step` | 46 | 13.0% |
| `sign_error` | 15 | 4.2% |
| `program_extracted_but_exec_fail` | 13 | 3.7% |
| `no_program_at_all` | 8 | 2.3% |
| `wrong_aggregate` | 2 | 0.6% |
| `format_ok_but_no_program` | 1 | 0.3% |

## Multi-Stage Curator Stats

| Stage | Metric | Count |
|-------|--------|-------|
| Stage 0.5 | Cluster quota full | 4 |
| Stage 1 | Quality gate passed | 14 |
| Stage 2 | Eval count | 13 |
| Stage 2 | Accept | 5 |
| Stage 2 | Reject (no improve) | 8 |
| Stage 2 | Reject (harmful) | 0 |
| Stage 3 | Pass dedup | 6 |
| Final | Accept | 6 |
| Auto-ablate | Calls | 7 |
| Auto-ablate | Evicted | 0 |
| Tier 1 | Promotions | 3 |
| Tier 1 | Fallback promotions | 2 |
| Lift evals | Rounds run | 13 |

## Verify-Iterate Stats

| Metric | Count |
|--------|-------|
| Total attempts | 353 |
| Round 1 pass | 11 |
| Round 2 pass | 3 |
| Round 3 pass | 4 |
| Total pass | 18 |
| Exhausted all rounds | 112 |
| Relaxed pass (R20.1) | 0 |
| Fewshot used | 375 |
| Reflector skipped (lucky) | 103 |
| Reflector skipped (correct) | 324 |

## Counterfactual Reflection

- Triggered: **336**
- Cases found: 335

## Top Bullets by Dev Lift (EMA)

| Bullet ID | PA-lift | EA-lift | n_evals | Tier 1 |
|-----------|---------|---------|---------|--------|
| `pg-00001` | +0.0214 | +0.0143 | 4 | 🔒 |
| `ns-00001` | +0.0141 | +0.0143 | 6 | 🔒 |
| `pg-00002` | +0.0139 | +0.0258 | 4 | 🔒 |
| `tr-00001` | -0.0188 | -0.0006 | 4 |  |
| `ns-00003` | -0.0276 | -0.0080 | 3 |  |
| `ns-00002` | -0.0354 | -0.0205 | 7 |  |

## Final Playbook Cluster Distribution

| Cluster | Bullets |
|---------|---------|
| `C12_misc_other` | 4 |
| `C8_sub_div_2step_other` | 1 |
| `C6_unit_no_conversion` | 1 |
