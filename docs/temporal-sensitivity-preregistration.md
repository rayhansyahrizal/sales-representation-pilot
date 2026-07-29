# Duplicate-feature and permutation sensitivity protocol

**Frozen before fitting on 2026-07-29 at 18:10:41 +07:00. EXPLORATORY — builder-accessible data; not confirmatory or hidden-holdout evidence.**

The exact protocol is `manifests/temporal-sensitivity-manifest.json`. This one-way sensitivity removes `purchase_frequency`, which is exactly identical to `unique_invoices`, while leaving the parent expanding-window logistic procedure unchanged. It also repeats the within-training-month permutation control for 100 pre-specified consecutive seeds at every evaluation cutoff. There is no tuning or model selection.

The ranking conclusion survives if duplicate-free PR-AUC gain is positive in at least 80% of cutoffs. The original September 2010 control excursion is considered compatible with permutation variability if at least 5% of repetitions produce a maximum monthly control gain at least as large. This threshold is descriptive, not a hypothesis test or confirmatory error guarantee. All relationships remain predictive associations among known prior purchasers, not causal effects.
