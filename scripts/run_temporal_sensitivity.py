#!/usr/bin/env python3
"""Run the frozen duplicate-feature and permutation sensitivity protocol."""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

import duckdb
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sales_representation_audit.stability import scalar_summary, temporal_binary_metrics

FEATURES = ["recency_days", "unique_invoices", "unique_items", "gross_quantity", "gross_value", "tenure_days", "calendar_month"]


def fit_predict(dev, ev, labels, seed):
    model = make_pipeline(
        SimpleImputer(strategy="median"), StandardScaler(),
        LogisticRegression(C=1.0, max_iter=500, random_state=seed),
    )
    model.fit(dev[FEATURES], labels)
    return model.predict_proba(ev[FEATURES])[:, 1], model[-1].coef_[0]


def permute_within_cutoff(dev, seed):
    labels = dev.label.to_numpy().copy()
    rng = np.random.default_rng(seed)
    for _, positions in dev.groupby("cutoff", sort=True).indices.items():
        labels[positions] = rng.permutation(labels[positions])
    return labels


def quantile_summary(values):
    values = np.asarray(values, dtype=float)
    return {"q05": float(np.quantile(values, 0.05)), "median": float(np.median(values)), "q95": float(np.quantile(values, 0.95))}


def main():
    manifest_path = ROOT / "manifests/temporal-sensitivity-manifest.json"
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    source = ROOT / manifest["source_feature_artifact"]
    con = duckdb.connect()
    episodes = con.execute(f"select * from read_parquet('{source}') order by cutoff, CustomerID").df()
    con.close()
    episodes["cutoff"] = pd.to_datetime(episodes.cutoff)
    assert episodes.purchase_frequency.equals(episodes.unique_invoices)
    cutoffs = sorted(episodes.cutoff.unique())
    seeds = range(manifest["seeds"]["first"], manifest["seeds"]["last"] + 1)
    monthly, coefficients, cohorts, control_by_seed = [], [], [], {seed: [] for seed in seeds}

    for raw_cutoff in cutoffs[6:]:
        cutoff = pd.Timestamp(raw_cutoff)
        eligible = [pd.Timestamp(x) for x in cutoffs if pd.Timestamp(x) + pd.Timedelta(days=30) <= cutoff]
        dev = episodes[episodes.cutoff.isin(eligible)].copy().reset_index(drop=True)
        ev = episodes[episodes.cutoff == cutoff].copy().reset_index(drop=True)
        assert (dev.cutoff + pd.Timedelta(days=30) <= cutoff).all()
        assert (ev.feature_max_timestamp < cutoff).all()
        reference = float(dev.label.mean())
        p, coef = fit_predict(dev, ev, dev.label.to_numpy(), manifest["seeds"]["first"])
        real = temporal_binary_metrics(ev.label, p, reference)
        real.update({"cutoff": cutoff.date().isoformat(), "training_rows": int(len(dev)), "training_cutoffs": len(eligible)})
        coefficients.append({"cutoff": real["cutoff"], **dict(zip(FEATURES, map(float, coef)))})

        control_gains, control_rocs = [], []
        for seed in seeds:
            pp, _ = fit_predict(dev, ev, permute_within_cutoff(dev, seed), seed)
            pm = temporal_binary_metrics(ev.label, pp, reference)
            control_gains.append(pm["pr_auc_gain"])
            control_rocs.append(pm["roc_auc"])
            control_by_seed[seed].append(pm["pr_auc_gain"])
        real["permutation_pr_auc_gain"] = quantile_summary(control_gains)
        real["permutation_roc_auc"] = quantile_summary(control_rocs)
        real["permutation_gain_ge_real_fraction"] = float(np.mean(np.asarray(control_gains) >= real["pr_auc_gain"]))
        monthly.append(real)

        groups = {
            "one_prior_invoice": ev.unique_invoices == 1,
            "multiple_prior_invoices": ev.unique_invoices > 1,
            "tenure_le_90_days": ev.tenure_days <= 90,
            "tenure_gt_90_days": ev.tenure_days > 90,
        }
        for name, mask in groups.items():
            if int(mask.sum()) >= 100 and ev.loc[mask, "label"].nunique() == 2:
                cohorts.append({"cutoff": real["cutoff"], "cohort": name, **temporal_binary_metrics(ev.loc[mask, "label"], p[mask.to_numpy()], reference)})

    max_control = [max(control_by_seed[seed]) for seed in seeds]
    threshold = manifest["original_september_2010_permutation_pr_auc_gain"]
    coef_summary = {}
    for feature in FEATURES:
        values = np.asarray([row[feature] for row in coefficients])
        majority = 1 if np.median(values) >= 0 else -1
        coef_summary[feature] = {**scalar_summary(values), "majority_sign": "positive" if majority == 1 else "negative", "majority_sign_fraction": float(np.mean(np.sign(values) == majority))}
    gains = [row["pr_auc_gain"] for row in monthly]
    result = {
        "label": "EXPLORATORY — builder-accessible evaluation data",
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "source_feature_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "monthly": monthly, "cohorts": cohorts, "coefficients": coefficients,
        "summary": {
            "evaluation_cutoffs": len(monthly), "permutation_repetitions": len(list(seeds)),
            "pr_auc_gain": scalar_summary(gains), "roc_auc": scalar_summary([x["roc_auc"] for x in monthly]),
            "brier_skill": scalar_summary([x["brier_skill"] for x in monthly]),
            "positive_pr_auc_gain_fraction": float(np.mean(np.asarray(gains) > 0)),
            "max_permutation_pr_auc_gain": quantile_summary(max_control),
            "familywise_excursion_ge_original_fraction": float(np.mean(np.asarray(max_control) >= threshold)),
            "coefficient_summary": coef_summary,
        },
    }
    out = ROOT / "artifacts/temporal-sensitivity"
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
