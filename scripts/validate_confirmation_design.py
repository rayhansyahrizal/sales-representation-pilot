"""Validate the frozen confirmation design without accessing any dataset."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "manifests" / "confirmation-design-v1.json"


def validate(manifest: dict, root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    required = {
        "protocol", "status", "evidence_boundary", "eligibility", "cutoffs",
        "model", "recalibration", "evaluation", "decision_thresholds",
        "falsification", "monitoring", "stop_rules", "required_locks_before_run",
    }
    errors.extend(f"missing top-level key: {key}" for key in sorted(required - manifest.keys()))
    if errors:
        return errors

    if manifest["status"] != "DESIGN_FROZEN_PENDING_DATASET_DECISION":
        errors.append("status must remain pending until a governed dataset decision")
    if manifest.get("operational_authority") is not False:
        errors.append("design must not grant operational authority")
    boundary = manifest["evidence_boundary"]
    prohibited = set(boundary.get("prohibited_confirmation_dataset_ids", []))
    if not {"online_retail_ii", "retailrocket_events"}.issubset(prohibited):
        errors.append("exploratory datasets must be prohibited from confirmation")
    if manifest["eligibility"].get("entity_overlap_with_exploration") != 0:
        errors.append("confirmation must require zero exploratory entity overlap")

    cutoff = manifest["cutoffs"]
    if cutoff.get("embargo_days") != manifest["eligibility"].get("horizon_days"):
        errors.append("label embargo must equal outcome horizon")
    if "last 6" not in cutoff.get("final_confirmation_rule", ""):
        errors.append("six-cutoff untouched confirmation block is not frozen")
    features = set(manifest["model"].get("features", []))
    forbidden = set(manifest["model"].get("forbidden_features", []))
    if features & forbidden:
        errors.append("a feature is both allowed and forbidden")
    if "purchase_frequency" not in forbidden:
        errors.append("known duplicate purchase_frequency must be forbidden")

    recal = manifest["recalibration"]
    if not recal.get("frozen_during_final_confirmation"):
        errors.append("recalibration must be frozen during final confirmation")
    if "did not train" not in recal.get("pool", ""):
        errors.append("calibration pool must require out-of-sample predictions")
    if manifest["evaluation"].get("seed") is None:
        errors.append("evaluation seed must be fixed")
    if len(manifest["stop_rules"]) < 5:
        errors.append("stop rules are incomplete")

    for relative, expected in boundary.get("exploratory_artifact_sha256", {}).items():
        path = root / relative
        if not path.is_file():
            errors.append(f"missing pinned exploratory artifact: {relative}")
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            errors.append(f"exploratory artifact hash changed: {relative}")
    return errors


def main() -> int:
    manifest = json.loads(MANIFEST.read_text())
    errors = validate(manifest)
    if errors:
        print("INVALID confirmation design")
        for error in errors:
            print(f"- {error}")
        return 1
    digest = hashlib.sha256(MANIFEST.read_bytes()).hexdigest()
    print(f"VALID confirmation design: {MANIFEST.relative_to(ROOT)} sha256={digest}")
    print("Execution state: BLOCKED_PENDING_DATASET_DECISION")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
