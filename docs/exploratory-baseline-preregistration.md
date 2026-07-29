# Exploratory baseline preregistration

**EXPLORATORY — builder-accessible evaluation data; not confirmatory or hidden-holdout evidence.**

This freezes the protocol in `manifests/exploratory-baseline-manifest.json` before model fitting. Online Retail uses valid identified prior purchasers at monthly cutoffs, strict prior-only G0 features, a 30-day outcome, earlier cutoffs for development, and the final complete cutoff for evaluation. Retailrocket uses visitor/timestamp groups, strictly later groups as targets, and an 80% chronological boundary. Models are restricted to prevalence, fixed regularized logistic regression, transition frequencies, and deterministic top-10 development popularity. Seed is 20260729 and customer bootstrap budget is exactly 2,000.

The future-feature validator must reject target/future columns. A seeded outcome-permutation logistic control must be chance-like. The mechanical rule is the exact `kill_rule` string in the manifest. Results can only motivate further independent testing; all claims remain exploratory and builder-accessible.
