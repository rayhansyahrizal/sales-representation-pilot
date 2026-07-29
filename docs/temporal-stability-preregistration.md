# Repeat-purchase temporal stability protocol

**Frozen before fitting on 2026-07-29 at 17:40:36 +07:00. EXPLORATORY — builder-accessible data; not confirmatory or hidden-holdout evidence.**

The exact protocol is `manifests/temporal-stability-manifest.json`. It evaluates the existing leakage-safe Online Retail II customer episodes at successive monthly origins. At each origin, an expanding-window fixed logistic model may use only monthly cohorts whose 30-day outcome has completed. No tuning or model selection is allowed.

The primary descriptive stability evidence is monthly PR-AUC gain over training prevalence, discrimination, Brier skill, calibration, and standardized coefficient signs. Results are also stratified by one versus multiple prior invoices and tenure at most 90 versus over 90 days, with groups below 100 episodes suppressed. Population/outcome drift is reported by month. A within-training-month label permutation is the frozen falsification control.

A predictor is described as stable only under the manifest's mechanical descriptive rule. This analysis predicts recorded repeat purchase among known prior purchasers; it does not estimate marketing effects, acquisition, customer intent, or causality. Repeated customers appear at multiple cutoffs, and all reported uncertainty/variation is descriptive across time rather than independent-sample inference.
