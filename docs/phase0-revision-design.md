# Phase 0 revision design: minimum defensible predictive tasks

**Status:** design only; no modeling or dataset modification. **Recommendation:** proceed only with the narrow administrative-log tasks below after the listed tests pass. The design does not identify exposure, recommendation effects, marketing effects, demand, or economic value.

## Evidence and scope

UCI describes Online Retail II as all recorded transactions of one UK non-store retailer from 2009-12-01 through 2011-12-09. It defines an invoice beginning with `C` as a cancellation, but provides no original-invoice key or matching rule; `CustomerID` can be missing.[1] The local audit consequently finds 22,950 negative-quantity lines, 19,494 `C`-prefix lines, incomplete linkage, and only 77.23% row-level customer-ID coverage.[2]

Retailrocket's publisher page describes implicit-feedback events (`view`, `addtocart`, `transaction`), millisecond timestamps, and item properties as time-dependent snapshots compressed to rows emitted when values change.[3] It does **not** provide impressions, stock/eligibility intervals, or a recommender's candidate set. The local audit confirms these absences.[4] Therefore “candidate” below means a reproducible **historically observed item universe**, never availability or exposure.

## Frozen units and labels

### Online Retail II: repeat recorded-purchase task

At a cutoff `c`, the risk set is exactly customers with a nonmissing `CustomerID` on at least one valid positive purchase line at time `< c`. Predict whether each such customer has at least one valid positive purchase invoice in `[c, c + 30 days)`. Require `c + 30 days <= dataset end`; features use only rows with time `< c`.

A valid positive purchase line has: non-`C` invoice, `Quantity > 0`, `UnitPrice >= 0`, nonmissing customer ID, and a non-administrative `StockCode`. Before confirmatory modeling, the deny set is frozen as `ADJUST`, `ADJUST2`, `AMAZONFEE`, `BANK CHARGES`, `CRUK`, `D`, `DOT`, `M`, `POST`, and `S`; it may not be revised from outcome performance. Aggregate the binary label at invoice level, then customer level. This is a **repeat recorded-purchase** label, not an eligible-customer conversion rate. Never include anonymous rows in the actor risk set, impute identity, or infer nonpurchase before a customer's first observed identified purchase. Report risk-set size and excluded/missing-ID row and invoice fractions for every split.

Cancellation ledger (audit and sensitivity, not backward feature rewriting):

1. Mark a line as cancellation-like if invoice starts with uppercase `C` after trimming **or** `Quantity < 0`; retain disagreements as a diagnostic stratum.
2. For a cancellation-like line with a customer ID, search only earlier positive lines of the same `CustomerID` and `StockCode`; require equal `UnitPrice` and remaining unmatched quantity sufficient to absorb `abs(Quantity)`. Allocate FIFO by original invoice time, recording one-to-many allocations. Never match across customers, use description, or use a later row.
3. Lines with missing customer ID, no qualifying predecessor, price conflict, or excess quantity remain unmatched/partially matched. Do not invent a link. Preserve raw event times; a cancellation observed after `c` cannot alter features at `c`.
4. Primary label remains gross recorded purchase (a later cancellation does not make the earlier event unknowable). Prespecified sensitivity A removes target-window positive quantity canceled by an observed linked cancellation through the dataset end; sensitivity B reports net linked quantity through `min(c+30 days+30 days, dataset end)` only for cutoffs with that extra follow-up. These are descriptive robustness checks, not “true retained sale” labels.

This is the smallest defensible rule because UCI documents the `C` indicator but not invoice linkage.[1] Exact original-invoice recovery is therefore unresolved, and any quantity/price match is analyst-derived.

### Retailrocket: next event and next historically observed item

Create one prediction episode immediately after an event `(visitor, item, event_type, t)`, using only rows with timestamp `<= t`; the target is that visitor's next event at time `t' > t`. If multiple events share a timestamp, impose no fabricated order: treat the timestamp group as one basket-like history update and target the next strictly later timestamp group. Exclude episodes with no observed next event from next-event evaluation as right-censored, and report their count.

* **Event-type task:** predict the type at `t'`; no item candidate set is needed.
* **Next-item task:** define `C(t)` as distinct items appearing in any event at timestamp `<= t`. The primary evaluable set contains episodes whose target item is in `C(t)`. Report unconditional target coverage `P(target item in C(t))` and a separate cold-start stratum for targets outside it; never score cold-start items as if rankable. `C(t)` is cumulative to avoid an unsupported inactivity/stock assumption. If computation requires negative sampling, sample only from `C(t)`, freeze the sampler/seed, and do not present sampled metrics as full-catalog Recall/NDCG.

This reconstructs an observable universe, not the site's actual assortment, impressions, or recommendation opportunity. No stronger candidate claim is supportable from the publisher schema.[3]

## Strict Retailrocket property join

For each episode time `t` and each `(itemid, property)`, attach the row with maximum property timestamp `p <= t` (backward as-of join). Never use `p > t`, global/latest values, backward fill, or information from another item. If no such row exists, emit an explicit missing indicator. When duplicate `(itemid, property, p)` rows disagree, mark the value ambiguous and exclude that property-value at and after `p` until a later unambiguous update; do not choose by file order. Exact equality is allowed because the property is recorded by the decision timestamp; a strict `< t` sensitivity must also be reported because ordering within the same millisecond is undocumented. Merge the two physical property files before ordering. Treat the category tree as static only, with an explicit unknown-validity limitation; it cannot establish historical item availability.[3]

## Hidden cutoff and horizon ownership

Before any model code or fitting, a named reproducer who is not the model builder must:

1. freeze dataset file hashes, timezone interpretation (Retailrocket Unix UTC; Online Retail II source-local/unspecified), episode rules, 30-day Online Retail horizon, Retailrocket “next strictly later timestamp” horizon, metrics, and final chronological boundaries in a canonical manifest;
2. retain the final time block physically outside the builder's accessible working tree and provide only development data ending before it;
3. publish a SHA-256 commitment to the canonical hidden manifest plus owner/date, while keeping boundaries and holdout rows private;
4. reveal once, only after code version, representations, metrics, seeds, and stopping rules are frozen; archive the revealed manifest and verify its commitment; and
5. invalidate the confirmatory run after any holdout-informed revision. Such a revision requires a newly owned holdout or is labeled exploratory.

The hidden block must include complete target follow-up: at least 30 days after each Online Retail cutoff and a recorded next timestamp for included Retailrocket episodes. Entity/cold-start slices are assignments frozen in the same hidden manifest, derived without outcomes.

## Gate tests required before modeling authorization

Automated fixture tests plus whole-data audit assertions must establish:

- **Online Retail:** no risk-set customer first appears at/after cutoff; all predictors are `< c`; labels are in `[c,c+30d)`; no anonymous identity is inferred; reconciliation never crosses customer/stock, never uses a future predecessor, conserves matched quantity, is deterministic under row shuffling, and exposes unmatched/partial/conflict rates. Test `C`/negative disagreement, missing ID, split cancellation, excess cancellation, equal timestamps, and horizon-edge cases.
- **Retailrocket properties:** joined key is identical; joined timestamp is `<= t`; the selected row is maximal; no-predecessor is missing; cross-file ordering is invariant; conflicting duplicates are ambiguous; equality and strict-`<` sensitivity differ only on ties. A deliberate future property must fail.
- **Retailrocket episodes/candidates:** target time is strictly later; tied events are grouped; every scored target belongs to `C(t)`; every candidate's first event is `<= t`; reconstruction is invariant to input order; cold-start coverage and right censoring are reported. A deliberate future item must fail.
- **Holdout governance:** file hashes and manifest commitment verify; builder cannot access holdout rows before freeze; horizon completeness passes; one-time reveal and any post-reveal change are logged.

## Unresolved ambiguities and decision

Unresolved but bounded limitations are: no documented Online Retail cancellation-to-original key or return reason; selective missing customer identity and no denominator of unobserved/nonbuying customers; unspecified Online Retail timezone; unknown same-millisecond order in Retailrocket; no impressions, inventory/eligibility intervals, property semantics, or historical category validity; and censoring at each source's end.

**Decision: conditionally scientifically viable for a narrow predictive pilot.** It is viable as (i) repeat *recorded* purchase among previously identified purchasers and (ii) next logged event/item within a historically observed item universe. It is **not** viable as customer acquisition, recommendation, causal marketing, demand, retained-sale, or profit research. Modeling remains unauthorized until the tests pass and independent holdout custody is evidenced. Failure to obtain independent physical holdout custody, unacceptable cancellation-match ambiguity for the planned sensitivity, or low next-item candidate coverage should stop or further narrow the affected task rather than expand scope.

## References

1. UCI Machine Learning Repository, **Online Retail II** dataset description and variable definitions, DOI 10.24432/C5CG6D: https://archive.ics.uci.edu/dataset/502/online+retail+ii
2. Local immutable Phase 0 audit: `artifacts/audits/online_retail_ii.json`.
3. Retail Rocket, **Retailrocket Recommender System Dataset**, publisher Kaggle page (events and time-dependent property/change-log documentation): https://www.kaggle.com/datasets/retailrocket/ecommerce-dataset
4. Local immutable Phase 0 audit: `artifacts/audits/retailrocket.json`.
5. Governing protocol: `../research/2026-07-29-sales-representation/falsification-pilot.md`, §§4, 6, 9.
