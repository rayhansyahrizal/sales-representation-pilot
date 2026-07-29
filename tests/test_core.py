import pandas as pd
from sales_representation_audit.core import missingness, identity_coverage, holdout_feasibility

def test_missingness_is_exact_and_zero_safe():
    d=pd.DataFrame({'a':[1,None], 'b':[None,None]})
    assert missingness(d)=={'a':{'count':1,'fraction':.5},'b':{'count':2,'fraction':1.0}}
    assert missingness(pd.DataFrame({'a':[]}))['a']['fraction']==0

def test_identity_coverage():
    d=pd.DataFrame({'u':[1,1,None], 'i':['x','y','y']})
    assert identity_coverage(d,'u','i')['actor']=={'column':'u','present_rows':2,'coverage':2/3,'unique':1}

def test_holdout_rule_is_deterministic_and_conservative():
    assert holdout_feasibility(1000,3,100,100,1,1)['entity']
    assert not holdout_feasibility(999,3,100,100,1,1)['chronological']
    assert not holdout_feasibility(1000,3,100,100,0,1)['entity']
