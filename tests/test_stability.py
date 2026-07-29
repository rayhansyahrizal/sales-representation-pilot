import numpy as np
import pytest

from sales_representation_audit.stability import safe_logit, scalar_summary, temporal_binary_metrics


def test_temporal_metrics_are_finite_and_rank_sensitive():
    y = np.array([0, 0, 1, 1])
    good = temporal_binary_metrics(y, [0.1, 0.2, 0.8, 0.9], 0.5)
    assert good["pr_auc"] == pytest.approx(1.0)
    assert good["roc_auc"] == pytest.approx(1.0)
    assert good["pr_auc_gain"] == pytest.approx(0.5)
    assert good["brier_skill"] > 0


def test_helpers_handle_boundaries_and_summarize():
    assert np.isfinite(safe_logit([0, 1])).all()
    assert scalar_summary([3, 1, 2]) == {"min": 1.0, "median": 2.0, "max": 3.0}
    with pytest.raises(ValueError, match="both outcome classes"):
        temporal_binary_metrics([1, 1], [0.8, 0.9], 0.5)
