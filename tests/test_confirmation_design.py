import copy
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "validate_confirmation_design", ROOT / "scripts" / "validate_confirmation_design.py"
)
assert SPEC is not None
assert SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def load_manifest():
    return json.loads((ROOT / "manifests" / "confirmation-design-v1.json").read_text())


def test_frozen_confirmation_design_is_valid():
    assert module.validate(load_manifest(), ROOT) == []


def test_exploratory_dataset_cannot_be_relabelled_confirmation():
    manifest = copy.deepcopy(load_manifest())
    manifest["evidence_boundary"]["prohibited_confirmation_dataset_ids"].remove("online_retail_ii")
    assert any("prohibited" in error for error in module.validate(manifest, ROOT))


def test_embargo_must_match_horizon_and_calibration_must_be_out_of_sample():
    manifest = copy.deepcopy(load_manifest())
    manifest["cutoffs"]["embargo_days"] = 0
    manifest["recalibration"]["pool"] = "all predictions"
    errors = module.validate(manifest, ROOT)
    assert any("embargo" in error for error in errors)
    assert any("out-of-sample" in error for error in errors)


def test_operational_authority_is_rejected():
    manifest = copy.deepcopy(load_manifest())
    manifest["operational_authority"] = True
    assert any("operational" in error for error in module.validate(manifest, ROOT))
