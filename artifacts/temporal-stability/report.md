# Temporal stability of repeat-purchase predictors

**EXPLORATORY — builder-accessible evaluation data. Not confirmatory, causal, or hidden-holdout evidence.**

## Result

Across 17 successive monthly cutoffs (July 2010–November 2011), the fixed expanding-window logistic model improved PR-AUC over each month's prevalence in **17/17 months**. Monthly PR-AUC gain ranged from **0.228 to 0.379** (median **0.320**); ROC-AUC ranged from **0.686 to 0.829** (median **0.778**). This satisfies the frozen descriptive stability rule for repeat-purchase signal.

The most directionally stable standardized coefficients were:

- **More recent purchasing**: recency coefficient was negative in 17/17 fits (median −0.329).
- **More prior invoices/purchases**: positive in 17/17 fits (median +0.464 for each duplicated invoice-count column).
- **More distinct items previously bought**: positive in 17/17 fits (median +0.170).
- Gross quantity was consistently negative but small (median −0.027), while gross value was positive in 15/17 fits and small at the median (+0.032).

`purchase_frequency` and `unique_invoices` are identical by construction, so their individual coefficients are not separately identifiable and must not be interpreted as two independent findings. The stable practical pattern is recency plus depth/breadth of prior purchase history—not a causal explanation.

## Cohorts

Customers with multiple prior invoices had a median monthly repeat-purchase prevalence of **25.4%**, versus **6.5%** for customers with exactly one prior invoice. Predictive ranking remained positive in every month in both groups, but was much weaker for one-invoice customers (median PR-AUC gain **0.069**, median ROC-AUC **0.662**) than for multiple-invoice customers (gain **0.302**, ROC-AUC **0.748**).

Median repeat prevalence was similar for tenure ≤90 days (**19.2%**) and >90 days (**19.9%**), showing that tenure alone does not explain the difference. Ranking was less stable/useful among newer-tenure customers (median ROC-AUC **0.655**, Brier skill **0.063**) than established-tenure customers (ROC-AUC **0.784**, Brier skill **0.196**).

## Important instability and falsification findings

Calibration was not fully stable. Calibration slopes ranged **0.603–0.946** (all below one), and January 2011 had negative Brier skill (**−0.265**) with calibration-in-the-large **−1.428** because observed prevalence fell to 14.8% while the expanding training prevalence was 27.8%. Ranking survived this shift (ROC-AUC 0.800), but unadjusted probabilities did not. A deployment would therefore require cutoff-aware recalibration and drift monitoring.

The within-training-month permutation control was generally near chance at the median (PR-AUC gain **0.015**, ROC-AUC **0.525**) but had a September 2010 excursion (gain **0.196**, ROC-AUC **0.663**). Thus the control materially weakens any claim that every monthly gain is uniquely attributable to stable individual-level relationships. The real model still exceeded the permuted gain in every month, but this is an exploratory falsification warning, not a pass suitable for confirmation.

## Conclusion

Previous customers are much more likely to buy again when their purchases are recent and their prior relationship has greater transaction depth and item breadth. Those ranking patterns are directionally stable across the observed months and broad cohorts, but **probability calibration is seasonally unstable**, one-invoice/new-tenure customers are harder to rank, duplicated invoice features limit coefficient interpretation, and the permutation excursion requires caution. Full machine-readable monthly, cohort, coefficient, and drift records are in `artifacts/temporal-stability/results.json`.
