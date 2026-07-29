# Phase 0 feature-availability register

| Dataset/field | Role | Available at event time? | Primary future-leakage rule |
|---|---|---:|---|
| Online Retail II Customer ID, country | actor/context | yes when recorded | fit identity/history only before cutoff |
| Invoice, stock, description, quantity, unit price | basket/object/outcome | at transaction | never use target-window basket fields as predictors |
| Invoice date | event time | yes | chronological split; history strictly before cutoff |
| Cancellation prefix / negative quantity | return outcome | after original purchase or contemporaneous | reconcile as outcome; never back-propagate into earlier features |
| Retailrocket visitor/item/event | actor/object/response | at event | histories strictly earlier than prediction cutoff |
| Retailrocket transaction ID | outcome | only at purchase | target/outcome only |
| Item properties timestamp/value | object state | from property timestamp | as-of backward join only; never latest/global value |
| Category tree | object hierarchy | release lacks validity intervals | treat as static with explicit limitation |

No action assignment, shown-item risk set, propensity, margin, return/fulfillment horizon, or nonbuyer denominator exists in either source.
