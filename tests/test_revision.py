import json
from pathlib import Path
import pandas as pd
import pytest
from sales_representation_audit.core import (
    build_online_labels, reconcile_cancellations, asof_properties,
    build_next_event_episodes, canonical_manifest_bytes, manifest_commitment,
    verify_manifest_commitment, check_horizon_completeness, holdout_governance_gate,
)


def online(rows):
    return pd.DataFrame(rows, columns=['line_id','InvoiceNo','StockCode','Quantity','InvoiceDate','UnitPrice','CustomerID'])


def test_online_risk_labels_boundaries_anonymous_and_admin():
    d=online([
      ('a','1','A',1,'2020-01-01',2,1), ('b','2','A',1,'2020-01-10',2,None),
      ('c','3','POST',1,'2020-01-11',2,1), ('d','4','A',1,'2020-01-11',2,1),
      ('e','5','A',1,'2020-02-10',2,1), ('f','6','A',1,'2020-01-11',2,2)])
    out=build_online_labels(d, '2020-01-11', dataset_end='2020-02-10', administrative_stockcodes={'POST'})
    assert out.labels.to_dict('records') == [{'CustomerID':1.0,'label':1}]
    assert out.diagnostics['risk_set_size']==1
    assert out.diagnostics['anonymous_rows']==1
    assert out.diagnostics['excluded_invoices_missing_id']==1
    assert out.diagnostics['predictor_max_time'] < pd.Timestamp('2020-01-11').isoformat()
    with pytest.raises(ValueError): build_online_labels(d, '2020-01-12', dataset_end='2020-02-10')


def test_fifo_reconciliation_all_cases_and_shuffle_determinism():
    d=online([
      ('p1','1','A',3,'2020-01-01',2,1), ('p2','2','A',2,'2020-01-02',2,1),
      ('split','C3','A',-4,'2020-01-03',2,1), ('excess','C4','A',-3,'2020-01-04',2,1),
      ('wrongcust','C5','A',-1,'2020-01-05',2,2), ('wrongstock','C6','B',-1,'2020-01-05',2,1),
      ('price','C7','A',-1,'2020-01-05',9,1), ('missing','C8','A',-1,'2020-01-05',2,None),
      ('disagree','9','Z',-1,'2020-01-05',1,1), ('tiepos','10','T',1,'2020-01-06',1,1),
      ('tiecan','C11','T',-1,'2020-01-06',1,1), ('futurepos','12','F',1,'2020-01-08',1,1),
      ('futurecan','C13','F',-1,'2020-01-07',1,1)])
    a=reconcile_cancellations(d); b=reconcile_cancellations(d.sample(frac=1,random_state=4))
    cols=['cancellation_id','positive_id','matched_quantity']
    assert a.allocations[cols].to_dict('records') == b.allocations[cols].to_dict('records')
    assert a.allocations.query("cancellation_id == 'split'")['matched_quantity'].tolist()==[3.0,1.0]
    assert a.diagnostics['matched_quantity']==5
    assert a.diagnostics['partial_lines']==1 and a.diagnostics['disagreement_lines']==1
    assert a.diagnostics['missing_customer_lines']==1 and a.diagnostics['price_conflict_lines']>=1
    assert not set(a.allocations.positive_id) & {'tiepos','futurepos'}
    assert a.diagnostics['quantity_conserved']


def props(rows): return pd.DataFrame(rows,columns=['source','itemid','property','timestamp','value'])

def test_property_asof_ambiguity_files_ties_and_future_guard():
    p=props([('b',1,'x',1,'old'),('a',1,'x',3,'same'),('b',1,'x',3,'conflict'),('a',1,'x',5,'new'),('a',2,'x',9,'future')])
    q=pd.DataFrame({'query_id':['early','tie','later','new','none'],'itemid':[1,1,1,1,3],'timestamp':[0,3,4,5,9]})
    le=asof_properties(q,p,strict=False); lt=asof_properties(q,p,strict=True)
    assert le.set_index('query_id').loc['early','missing']
    assert le.set_index('query_id').loc['tie','ambiguous'] and le.set_index('query_id').loc['later','ambiguous']
    assert le.set_index('query_id').loc['new','value']=='new'
    assert lt.set_index('query_id').loc['tie','value']=='old'
    pd.testing.assert_frame_equal(le,asof_properties(q,p.sample(frac=1,random_state=2),strict=False))
    bad=le.copy(); bad.loc[0,'property_timestamp']=99
    with pytest.raises(AssertionError): asof_properties(q,p,validate_result=bad)


def test_episodes_group_ties_candidates_cold_start_censor_and_shuffle():
    e=pd.DataFrame([
      (1,10,'view',1),(1,11,'view',1),(2,99,'view',2),(1,12,'cart',3),
      (1,10,'buy',4),(3,77,'view',5)],columns=['visitorid','itemid','event','timestamp'])
    a=build_next_event_episodes(e); b=build_next_event_episodes(e.sample(frac=1,random_state=9))
    pd.testing.assert_frame_equal(a.episodes,b.episodes)
    assert len(a.episodes)==2 and a.diagnostics['right_censored_groups']==3
    assert a.diagnostics['cold_start_episodes']==1
    assert (a.episodes.target_timestamp>a.episodes.timestamp).all()
    assert a.episodes.query('scorable').candidate_contains_target.all()
    assert a.diagnostics['candidate_first_event_violations']==0
    bad=a.episodes.copy(); bad.loc[bad.index[0],['candidate_contains_target','scorable']]=[False,True]
    with pytest.raises(AssertionError): build_next_event_episodes(e,validate_result=bad)


def test_manifest_commitment_horizons_and_governance(tmp_path):
    m={'owner':'independent','created_at':'2026-01-01','dataset_hashes':{'x':'a'*64},'timezone':{'retailrocket':'UTC'},
       'rules':{'online_horizon_days':30,'retailrocket_target':'next_strictly_later'},'boundaries':{'private':'REDACTED'}}
    c=manifest_commitment(m)
    assert verify_manifest_commitment(m,c) and canonical_manifest_bytes(m)==canonical_manifest_bytes(json.loads(json.dumps(m)))
    assert not verify_manifest_commitment({**m,'owner':'changed'},c)
    assert check_horizon_completeness('online','2020-01-01','2020-01-31')['complete']
    assert not check_horizon_completeness('online','2020-01-02','2020-01-31')['complete']
    assert check_horizon_completeness('retailrocket',episodes_have_next=True)['complete']
    state={'commitment':c,'owner':'independent','builder':'builder','physical_custody_evidenced':False,'reveals':[],'post_reveal_changes':[]}
    gate=holdout_governance_gate(m,state)
    assert not gate['pass'] and 'physical_custody_not_evidenced' in gate['failures']
    state.update(physical_custody_evidenced=True); assert holdout_governance_gate(m,state)['pass']
    state['reveals']=[{'at':'x'},{'at':'y'}]; assert not holdout_governance_gate(m,state)['pass']
