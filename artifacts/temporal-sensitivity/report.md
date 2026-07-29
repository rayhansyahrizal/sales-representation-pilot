# Duplicate-feature and permutation sensitivity

**EXPLORATORY — builder-accessible evaluation data. Not confirmatory, causal, or hidden-holdout evidence.**

## Frozen decisions

This analysis followed `manifests/temporal-sensitivity-manifest.json`, committed before fitting. It removed `purchase_frequency` because it is exactly identical to `unique_invoices`; all other expanding-window model and evaluation choices were unchanged. It also evaluated 100 pre-specified within-training-month label permutations at every monthly cutoff, with no tuning.

## Duplicate removal result

The conclusion is effectively unchanged. The duplicate-free model had positive PR-AUC gain in **17/17 cutoffs** (frozen survival threshold: at least 80%). Gain ranged **0.228–0.379** with median **0.320**; ROC-AUC ranged **0.686–0.829** with median **0.778**. These values agree with the parent analysis to displayed precision. Calibration limitations also remain: median Brier skill was **0.193**, with a minimum of **−0.265**.

After removing the duplicate, standardized `unique_invoices` coefficients were positive in **17/17 fits** (median **+0.926**, range +0.838 to +0.962). The approximately doubled coefficient relative to either duplicated column in the parent fit demonstrates why the earlier individual duplicate coefficients were not separately interpretable. Recency remained negative in 17/17 fits (median **−0.328**) and unique items remained positive in 17/17 (median **+0.171**). This is coefficient-direction stability, not causal importance.

## Permutation excursion result

The original single-run September 2010 control gain of 0.196 is **compatible with the frozen repeated-permutation variability rule**: **25/100** pre-specified permutation repetitions had a maximum monthly control PR-AUC gain at least 0.196 (threshold: 5%). Across each repetition's worst monthly excursion, the median maximum gain was **0.131**, and the 5th–95th percentile range was **0.028–0.277**.

This resolves the excursion as not unusual under this particular repeated control, rather than validating every monthly association. The repeated statistic selects the maximum over 17 cutoffs, and the 100 runs are a descriptive sensitivity analysis—not a formal p-value, multiplicity correction, or hidden test. Per-cutoff control quantiles and fractions exceeding the real model are recorded in `results.json`.

## Bottom line

The stable predictive pattern survives removal of the duplicated invoice feature. Recent purchasing, more prior invoices, and broader item history remain consistently associated with stronger repeat-purchase ranking over time. The prior permutation warning is materially softened because excursions of its size occurred in 25% of fixed repeated controls, while the existing warnings about probability calibration, weaker one-invoice/new-tenure ranking, builder-accessible evaluation, and non-causal interpretation remain.
