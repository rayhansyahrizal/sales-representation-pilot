# Lean exploratory baseline result

**EXPLORATORY — builder-accessible evaluation data**

## Mechanical decision: PROCEED

Frozen kill-rule inputs: Online logistic PR-AUC gain `0.334249` (95% customer-bootstrap delta CI `[0.31201193189692256, 0.35649366172048086]`); Retailrocket transition accuracy gain `0.000000`; task-specific permutation control pass `True`; both datasets technically evaluable `True`. The Online gain fell to `0.048796` under permutation (less than half the real gain) with chance-like ROC-AUC `0.439880`; the qualifying real gain was removed materially.

Online evaluation at `2011-11-01T00:00:00` had 5,636 customer episodes. Logistic PR-AUC was `0.594895` versus prevalence `0.260646`. Retailrocket evaluated 269,087 chronological episodes; transition accuracy was `0.930104` versus global `0.930104`. Candidate coverage was `0.973250` and fixed development-popularity Recall@10 was `0.007244`.

Next-item ranking uses the preregistered bounded compromise: deterministic development-only top-10 popularity on covered episodes, not a full item scorer. These are hypothesis-generating builder-accessible results, not hidden-holdout or confirmatory evidence.
