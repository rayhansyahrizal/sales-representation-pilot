#!/usr/bin/env python3
"""Run the frozen expanding-window repeat-purchase stability protocol."""
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
from sales_representation_audit.exploratory import FEATURES
from sales_representation_audit.stability import scalar_summary, temporal_binary_metrics

SEED = 20260729


def fit_predict(dev, ev, labels=None):
    y = dev.label.to_numpy() if labels is None else np.asarray(labels)
    model = make_pipeline(
        SimpleImputer(strategy="median"),
        StandardScaler(),
        LogisticRegression(C=1.0, max_iter=500, random_state=SEED),
    )
    model.fit(dev[FEATURES], y)
    return model.predict_proba(ev[FEATURES])[:, 1], model[-1].coef_[0]


def main():
    manifest_path = ROOT / "manifests/temporal-stability-manifest.json"
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    source = ROOT / manifest["source_feature_artifact"]
    con = duckdb.connect()
    episodes = con.execute(f"select * from read_parquet('{source}') order by cutoff, CustomerID").df()
    con.close()
    episodes["cutoff"] = pd.to_datetime(episodes.cutoff)
    cutoffs = sorted(episodes.cutoff.unique())
    monthly, coefficients, cohort_rows, drift = [], [], [], []
    rng = np.random.default_rng(SEED)

    for evaluation_cutoff in cutoffs[6:]:
        evaluation_cutoff = pd.Timestamp(evaluation_cutoff)
        eligible_cutoffs = [pd.Timestamp(x) for x in cutoffs if pd.Timestamp(x) + pd.Timedelta(days=30) <= evaluation_cutoff]
        dev = episodes[episodes.cutoff.isin(eligible_cutoffs)].copy()
        ev = episodes[episodes.cutoff == evaluation_cutoff].copy().reset_index(drop=True)
        assert (dev.cutoff + pd.Timedelta(days=30) <= evaluation_cutoff).all()
        assert (ev.feature_max_timestamp < evaluation_cutoff).all()
        p, coef = fit_predict(dev, ev)
        reference = float(dev.label.mean())
        metrics = temporal_binary_metrics(ev.label, p, reference)
        metrics.update({"cutoff": evaluation_cutoff.date().isoformat(), "training_rows": int(len(dev)), "training_cutoffs": len(eligible_cutoffs)})

        permuted = dev.label.to_numpy().copy()
        # Preserve each training month's prevalence and season structure.
        for _, idx in dev.groupby("cutoff", sort=True).groups.items():
            positions = dev.index.get_indexer(idx)
            permuted[positions] = rng.permutation(permuted[positions])
        pp, _ = fit_predict(dev, ev, permuted)
        pm = temporal_binary_metrics(ev.label, pp, reference)
        metrics["permutation_pr_auc_gain"] = pm["pr_auc_gain"]
        metrics["permutation_roc_auc"] = pm["roc_auc"]
        monthly.append(metrics)
        coefficients.append({"cutoff": metrics["cutoff"], **{name: float(value) for name, value in zip(FEATURES, coef)}})

        groups = {
            "one_prior_invoice": ev.purchase_frequency == 1,
            "multiple_prior_invoices": ev.purchase_frequency > 1,
            "tenure_le_90_days": ev.tenure_days <= 90,
            "tenure_gt_90_days": ev.tenure_days > 90,
        }
        for name, mask in groups.items():
            if int(mask.sum()) >= manifest["minimum_cohort_reporting_n"] and ev.loc[mask, "label"].nunique() == 2:
                cm = temporal_binary_metrics(ev.loc[mask, "label"], p[mask.to_numpy()], reference)
                cohort_rows.append({"cutoff": metrics["cutoff"], "cohort": name, **cm})

        drift.append({
            "cutoff": metrics["cutoff"], "n": int(len(ev)), "prevalence": float(ev.label.mean()),
            **{f"median_{f}": float(ev[f].median()) for f in FEATURES if f != "calendar_month"},
        })

    gains = [x["pr_auc_gain"] for x in monthly]
    real_rocs = [x["roc_auc"] for x in monthly]
    perm_gains = [x["permutation_pr_auc_gain"] for x in monthly]
    perm_rocs = [x["permutation_roc_auc"] for x in monthly]
    coefficient_summary = {}
    for feature in FEATURES:
        values = np.array([x[feature] for x in coefficients])
        majority = 1 if np.median(values) >= 0 else -1
        coefficient_summary[feature] = {
            **scalar_summary(values),
            "majority_sign": "positive" if majority == 1 else "negative",
            "majority_sign_fraction": float(np.mean(np.sign(values) == majority)),
        }
    stable_features = [k for k, v in coefficient_summary.items() if v["majority_sign_fraction"] >= 0.8]
    result = {
        "label": "EXPLORATORY — builder-accessible evaluation data",
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "source_feature_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "evaluation_cutoffs": len(monthly),
        "monthly": monthly,
        "cohorts": cohort_rows,
        "coefficients": coefficients,
        "drift": drift,
        "summary": {
            "pr_auc_gain": scalar_summary(gains),
            "roc_auc": scalar_summary(real_rocs),
            "brier_skill": scalar_summary([x["brier_skill"] for x in monthly]),
            "calibration_slope": scalar_summary([x["calibration_slope"] for x in monthly]),
            "positive_pr_auc_gain_fraction": float(np.mean(np.array(gains) > 0)),
            "permutation_pr_auc_gain": scalar_summary(perm_gains),
            "permutation_roc_auc": scalar_summary(perm_rocs),
            "stable_coefficient_sign_features": stable_features,
            "coefficient_summary": coefficient_summary,
        },
    }
    out = ROOT / "artifacts/temporal-stability"
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
