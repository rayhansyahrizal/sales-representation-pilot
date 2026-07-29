import hashlib
import json
from pathlib import Path


def test_temporal_sensitivity_artifact_matches_frozen_protocol():
    manifest_path = Path("manifests/temporal-sensitivity-manifest.json")
    manifest = json.loads(manifest_path.read_text())
    result = json.loads(Path("artifacts/temporal-sensitivity/results.json").read_text())
    assert result["manifest_sha256"] == hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    assert manifest["exploratory"] and not manifest["confirmatory"]
    assert "purchase_frequency" not in manifest["features"]
    assert manifest["repetitions"] == 100
    assert result["summary"]["evaluation_cutoffs"] == 17
    assert result["summary"]["permutation_repetitions"] == 100
    assert len(result["monthly"]) == 17
    assert len(result["coefficients"]) == 17
    assert all("purchase_frequency" not in row for row in result["coefficients"])
    assert all(row["permutation_pr_auc_gain"]["q05"] <= row["permutation_pr_auc_gain"]["median"] <= row["permutation_pr_auc_gain"]["q95"] for row in result["monthly"])


def test_temporal_sensitivity_frozen_decision_rules_are_computable():
    result = json.loads(Path("artifacts/temporal-sensitivity/results.json").read_text())
    summary = result["summary"]
    assert 0 <= summary["positive_pr_auc_gain_fraction"] <= 1
    assert 0 <= summary["familywise_excursion_ge_original_fraction"] <= 1
    assert summary["positive_pr_auc_gain_fraction"] >= 0.8
