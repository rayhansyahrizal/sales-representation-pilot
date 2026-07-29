"""Deterministic helpers for exploratory temporal stability analysis."""
from __future__ import annotations

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, log_loss, roc_auc_score


def safe_logit(p):
    p = np.clip(np.asarray(p, dtype=float), 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def temporal_binary_metrics(y, p, reference_probability):
    y = np.asarray(y, dtype=int)
    p = np.clip(np.asarray(p, dtype=float), 1e-9, 1 - 1e-9)
    p0 = np.full(len(y), float(reference_probability))
    if len(np.unique(y)) != 2:
        raise ValueError("metrics require both outcome classes")
    n = max(1, int(np.ceil(len(y) * 0.1)))
    selected = np.argsort(-p, kind="mergesort")[:n]
    slope_model = LogisticRegression(penalty=None, solver="lbfgs", max_iter=500)
    slope_model.fit(safe_logit(p).reshape(-1, 1), y)
    brier = brier_score_loss(y, p)
    brier0 = brier_score_loss(y, p0)
    prevalence = float(y.mean())
    return {
        "n": int(len(y)),
        "positives": int(y.sum()),
        "prevalence": prevalence,
        "reference_probability": float(reference_probability),
        "pr_auc": float(average_precision_score(y, p)),
        "pr_auc_gain": float(average_precision_score(y, p) - prevalence),
        "roc_auc": float(roc_auc_score(y, p)),
        "brier": float(brier),
        "brier_skill": float(1 - brier / brier0),
        "log_loss": float(log_loss(y, p)),
        "calibration_in_large": float(safe_logit([prevalence])[0] - safe_logit([p.mean()])[0]),
        "calibration_slope": float(slope_model.coef_[0, 0]),
        "precision_at_10pct": float(y[selected].mean()),
        "recall_at_10pct": float(y[selected].sum() / y.sum()),
    }


def scalar_summary(values):
    x = np.asarray(values, dtype=float)
    return {"min": float(x.min()), "median": float(np.median(x)), "max": float(x.max())}
