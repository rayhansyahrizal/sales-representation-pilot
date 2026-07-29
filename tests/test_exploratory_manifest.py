import json
from pathlib import Path
from sales_representation_audit.core import manifest_commitment
from sales_representation_audit.exploratory import validate_availability

def test_manifest_and_future_control():
    m=json.loads(Path('manifests/exploratory-baseline-manifest.json').read_text())
    assert m['exploratory'] and not m['confirmatory'] and m['seed']==20260729 and m['bootstrap_resamples']==2000
    assert len(manifest_commitment(m))==64
    try: validate_availability(['recency_days','target_event'])
    except ValueError: pass
    else: raise AssertionError('future feature accepted')
