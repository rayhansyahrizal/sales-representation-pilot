# 0001: No confirmatory claims without a holdout the builder cannot see

Date: 2026-07-29. Status: accepted.

## Context

Both datasets are public, and I could read all of them while building features and models. Any result
measured on that data can be tuned, even unintentionally, by choices made after looking at it.

## Decision

- Every result in this repo is labelled **exploratory**.
- The modeling gate stays at **REVISE** until there is a holdout whose boundary is committed by someone
  other than the builder and stored where the builder cannot read it.
- A file inside this repo cannot prove that, so the gate does not accept one as proof.

## Consequences

- The repeat-purchase signal (17 of 17 months above prevalence) is reported as a strong hypothesis, not a
  finding.
- The Retailrocket next-step result (no gain over the most common transition) is reported as a negative
  result and not re-tried with different settings.
- The confirmation design is written and frozen (`docs/confirmation-governance-and-recalibration.md`), but
  not executed.
