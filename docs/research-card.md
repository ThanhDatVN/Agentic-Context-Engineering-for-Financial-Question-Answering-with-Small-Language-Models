# Research card

## Intended use

ACE-FinQA is intended for research on context adaptation, executable numerical reasoning, memory curation, and evaluation of small language models. The CPU package is suitable for inspecting FinQA data, testing DSL programs, validating prediction formats, and auditing the published result record.

## Out of scope

- financial advice, trading, credit, underwriting, accounting sign-off, or automated high-impact decisions;
- production processing of private financial documents;
- claims of end-to-end retrieval performance;
- claims that the stored scores are official FinQA leaderboard results;
- use of generated programs without independent execution and domain review.

## Data and privacy

The bundled data is the public FinQA benchmark derived from financial reports. New users must verify upstream terms and avoid mixing it with confidential filings or customer data. Per-example prediction logs reproduce benchmark questions and should not be copied into unrelated datasets without preserving provenance.

## Main risks

- **Arithmetic and program errors:** syntactically plausible programs may use the wrong values, operations, order, or units.
- **Lucky guesses:** an incorrect program can coincidentally execute to the expected answer.
- **Evaluator inflation:** permissive parsing or tolerance can overstate accuracy.
- **Oracle-context leakage:** annotated evidence makes the task easier than production retrieval.
- **Non-deterministic training:** API-backed reflection can change across runs even at temperature zero.
- **Domain overreach:** a FinQA result does not establish reliability on current reports, other jurisdictions, or real decisions.
- **Supply-chain exposure:** notebooks install and execute GPU/model packages from external sources.

## Mitigations in this repository

- a fail-closed CPU DSL executor and tests for invalid references, percent literals, and table rows;
- explicit separation of audited historical, `strict-v1`, and thesis-reported metrics;
- immutable result policy and provenance checklist;
- stripped notebooks, secret policy, and CPU CI;
- disclosure of oracle context, API-assisted training, and unsupported claims;
- human oversight and non-advice warnings.

## Known evidence gaps

The study covers one small language model and one benchmark. The main run is effectively single-seed, multi-step test buckets are small, data-contamination risk is unmeasured, and no expert user study is included. The thesis headline/result tables and configuration narrative also conflict with retained artifacts; see [`results/audit.md`](../results/audit.md). These gaps should be addressed before deployment or broad generalization.
