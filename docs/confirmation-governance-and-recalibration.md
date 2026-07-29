# Confirmation dataset governance and cutoff-aware recalibration v1

**Design frozen; no confirmation dataset has been selected or accessed.** The machine-readable authority is `manifests/confirmation-design-v1.json`. This package designs a future test; it does not upgrade, rerun, or relabel any existing evidence. All existing Online Retail II and Retailrocket results remain **EXPLORATORY — builder-accessible**.

## 1. Evidence boundary and governance

The confirmation custodian (not the analyst who developed the exploratory model) must approve and snapshot either (a) a genuinely separate, entity-disjoint source not previously inspected, or (b) a prospectively accumulated vintage whose events did not exist at this design freeze. Online Retail II, Retailrocket, derived episodes, and all resplits of them are prohibited. Public availability does not make previously inspected data confirmatory.

Before analyst access, the custodian records: owner; lawful basis/license; collection purpose; source and extract dates; field dictionary; source timezone; immutable raw SHA-256; row/customer/date bounds; duplicate policy; and an entity-disjointness audit. Use pseudonymous stable customer IDs. Retain only fields required by the manifest, apply repository/raw-data ignore controls, and publish aggregates only. No new private data is authorized by this design.

Roles and change control:

- **Custodian:** selects/snapshots data, verifies provenance and disjointness, withholds the last six eligible cutoffs, and releases only after code/manifest lock.
- **Analyst:** may develop plumbing against schemas or synthetic fixtures and earlier confirmation cutoffs, but cannot see final-cutoff outcomes or metrics before lock.
- **Reviewer:** verifies hashes, eligibility inventory, leakage tests, commit, environment, and signed manifest hash before release.
- Any endpoint, feature, exclusion, model, calibrator, threshold, or cutoff change creates v2 and requires a new untouched prospective window. It may not be justified against v1 final outcomes.

A dataset decision record must say `APPROVE`, `REJECT`, or `DEFER`, identify the custodian/reviewer, and map every eligibility requirement to evidence. Until APPROVE, execution is blocked.

## 2. Cohort, endpoint, and leakage-safe cutoffs

At each UTC calendar-month start, include known customers with at least one non-return purchase strictly before the cutoff. Features use events with `event_timestamp < cutoff`; the binary endpoint is a non-return purchase in `[cutoff, cutoff + 30 days)`. Anonymous and returns-only histories, unresolved timestamp ordering, and incomplete horizons are excluded.

Training at cutoff *t* may use only episodes whose 30-day outcome window has ended by *t*. This 30-day label embargo prevents partially observed outcomes. The same customer can occur at multiple historical cutoffs, so uncertainty resamples customers—not rows—and no episode from an evaluated cutoff may train its model. The last six eligible cutoffs form one untouched confirmation block. All prior eligible cutoffs are development-only. At least 12 complete cutoffs, 5,000 episodes, and 500 positives are required before partitioning.

The fixed duplicate-free feature set is recency, unique invoices, unique items, gross quantity/value, tenure, and calendar month. `purchase_frequency` is prohibited because exploration established it duplicates unique invoices. Customer IDs and all post-cutoff/future-derived values are forbidden. Deterministic timestamp-boundary and feature-lineage validators are gates, not warnings.

## 3. Frozen fit and recalibration procedure

For each cutoff, fit the existing fixed-preprocessing logistic regression on expanding eligible history. Preserve its decision score for ranking. Probability recalibration is strictly time nested:

1. For each development cutoff, generate predictions from a model trained only on earlier, fully matured episodes.
2. Before cutoff *t*, pool predictions/outcomes from at most the six most recent completed development cutoffs. Never use an episode's in-sample prediction.
3. Fit logistic intercept-and-slope calibration (`logit(y) ~ 1 + logit(p)`), using only this pool. With fewer than 200 positives, fit intercept-only prevalence correction; if fitting fails, use identity and record failure.
4. Freeze the mapping before scoring *t*. During the final six-cutoff confirmation block, execute this prespecified rolling procedure; never tune its window or method from final outcomes.

Report raw and recalibrated probability metrics. Recalibration cannot alter ranking, top-decile membership, or rescue a failed ranking claim. This design explicitly addresses the exploratory seasonal miscalibration without retrospectively calling the remedy confirmed.

## 4. Evaluation, falsification, and decisions

The primary statistic is the macro-average across final cutoffs of PR-AUC minus that cutoff's prevalence. Use a fixed-seed, 2,000-resample customer-cluster bootstrap for a two-sided 95% interval. Report every secondary metric and every cutoff; a missing metric fails the protocol.

**Ranking passes** only with gain ≥0.10, CI lower bound >0, and positive gains in at least five of six cutoffs. **Calibration passes** only if aggregate recalibrated Brier skill >0, ECE ≤0.05, slope 0.8–1.2, intercept −0.1–0.1, and no cutoff has negative Brier skill. Segment guardrails require positive gain in one-/multi-invoice and <90-/≥90-day tenure groups when each contains ≥100 positives; an underpowered or failed guardrail yields INCONCLUSIVE, not silent pooling.

The evaluation-only policy threshold is the top 10% of scores each cutoff, with the manifest's deterministic hash tie-break. It does not authorize contact, spend, or deployment. Report precision and recall there.

Run all frozen falsifications: injected future features must be rejected; within-training-cutoff permutation and customer-ID-hash gains must each be ≤0.02 with intervals containing zero; a +30-day timestamp shift must fail eligibility. Failure means overall FAIL. Overall CONFIRM requires ranking, calibration, falsification, and segment gates; all other outcomes are FAIL or INCONCLUSIVE. No causal claim is permitted.

## 5. Drift and monitoring

Use pooled development cutoffs as reference. Per cutoff record counts, prevalence, missingness, unseen categories, per-feature PSI, primary/segment discrimination, Brier skill, ECE, intercept, and slope. Quarantine on any manifest alert: PSI >0.20, prevalence outside the reference 99% binomial interval, Brier skill <0, ECE >0.05, slope outside 0.8–1.2, or episode-count shift >30%. Investigate lineage; do not adapt to confirmation outcomes. Post-confirmation monitoring is a design recommendation, not deployment approval.

## 6. Auditable implementation checklist

- [ ] Dataset decision record approved by named custodian and reviewer.
- [ ] License/lawful basis, provenance, field dictionary, and retention documented.
- [ ] Raw snapshot hash, extract bounds, timezone conversion, and source clock semantics locked.
- [ ] Zero entity overlap with exploratory sources demonstrated; prohibited datasets rejected.
- [ ] Cutoff inventory proves ≥12 complete months, ≥5,000 episodes, ≥500 positives.
- [ ] Last six cutoffs and all their outcomes/metrics withheld from analyst.
- [ ] Schema, return handling, deduplication, boundary, maturity, and lineage validators pass.
- [ ] Synthetic-fixture tests cover exact-boundary events, incomplete horizons, repeated customers, and future injection.
- [ ] Fixed feature/model code, nested prediction ledger, calibrator fallback, bootstrap, tie-break, and falsifications implemented.
- [ ] Code commit, `uv.lock`, manifest hash, dataset hash, seed, and reviewer sign-off locked before release.
- [ ] Run emits per-cutoff immutable prediction ledger, eligibility/audit report, calibration parameters, metrics, falsifications, drift report, and decision record.
- [ ] Any stop rule produces a terminal report without exploratory substitution, post-hoc repair, contact, or deployment.

## Current blocker / next decision

No eligible confirmation snapshot or custodian decision exists in this repository. That is the intentional stop boundary. The next human decision is to approve/reject/defer a qualifying source or prospective collection plan and assign an independent custodian/reviewer. Dataset acquisition, private-data access, and confirmation execution are out of scope until then.
