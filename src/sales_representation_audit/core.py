"""Pure, deterministic Phase-0 data-governance helpers.  No model code."""
from __future__ import annotations
from dataclasses import dataclass
from collections import defaultdict, deque
import hashlib, json
import pandas as pd


def missingness(df: pd.DataFrame) -> dict:
    n=len(df)
    return {str(c): {'count':int(df[c].isna().sum()), 'fraction': (float(df[c].isna().sum()/n) if n else 0.0)} for c in df.columns}


def identity_coverage(df, actor, obj):
    n=len(df)
    def one(col):
        present=int(df[col].notna().sum())
        return {'column':col,'present_rows':present,'coverage':float(present/n) if n else 0.0,'unique':int(df[col].nunique(dropna=True))}
    return {'actor':one(actor),'object':one(obj)}


def holdout_feasibility(n_rows, n_times, n_actor, n_object, actor_repeat, object_repeat):
    chronological=n_rows>=1000 and n_times>=3
    entity=n_actor>=100 and n_object>=100 and actor_repeat>0 and object_repeat>0
    return {'chronological':chronological,'entity':entity,
      'basis':{'rows':int(n_rows),'distinct_timestamps':int(n_times),'actors':int(n_actor),'objects':int(n_object),'repeated_actor_rows':int(actor_repeat),'repeated_object_rows':int(object_repeat)}}


@dataclass
class OnlineLabels:
    labels: pd.DataFrame
    diagnostics: dict


def _valid_positive(df, denied):
    inv=df.InvoiceNo.astype('string').str.strip()
    return (~inv.str.startswith('C',na=False) & (pd.to_numeric(df.Quantity,errors='coerce')>0) &
            (pd.to_numeric(df.UnitPrice,errors='coerce')>=0) & df.CustomerID.notna() &
            ~df.StockCode.astype('string').isin(denied))


def build_online_labels(df, cutoff, *, dataset_end=None, administrative_stockcodes=frozenset(), horizon_days=30):
    """Identified prior-purchaser risk set and gross invoice/customer binary label."""
    d=df.copy(); d['InvoiceDate']=pd.to_datetime(d.InvoiceDate); c=pd.Timestamp(cutoff)
    end=pd.Timestamp(dataset_end) if dataset_end is not None else d.InvoiceDate.max()
    h=c+pd.Timedelta(days=horizon_days)
    if h>end: raise ValueError('incomplete Online Retail target horizon')
    valid=_valid_positive(d,set(map(str,administrative_stockcodes)))
    prior=d[valid & (d.InvoiceDate<c)]
    risk=pd.Index(sorted(prior.CustomerID.unique()),name='CustomerID')
    target=d[valid & (d.InvoiceDate>=c) & (d.InvoiceDate<h) & d.CustomerID.isin(risk)]
    # Explicit invoice aggregation prevents line count from changing the binary outcome.
    positives=(target[['CustomerID','InvoiceNo']].drop_duplicates().groupby('CustomerID').size()>0)
    labels=pd.DataFrame({'CustomerID':risk, 'label':[int(positives.get(x,False)) for x in risk]})
    missing=d.CustomerID.isna(); miss_inv=d.loc[missing,'InvoiceNo'].nunique(dropna=True)
    diag={'risk_set_size':len(risk),'positive_labels':int(labels.label.sum()),
          'anonymous_rows':int(missing.sum()),'anonymous_row_fraction':float(missing.mean()) if len(d) else 0,
          'excluded_invoices_missing_id':int(miss_inv),
          'excluded_invoice_missing_id_fraction':float(miss_inv/d.InvoiceNo.nunique(dropna=True)) if d.InvoiceNo.nunique(dropna=True) else 0,
          'cutoff':c.isoformat(),'horizon_end_exclusive':h.isoformat(),
          'predictor_max_time':prior.InvoiceDate.max().isoformat() if len(prior) else None,
          'all_predictors_strictly_before_cutoff':bool(prior.empty or prior.InvoiceDate.max()<c)}
    return OnlineLabels(labels,diag)


@dataclass
class Reconciliation:
    allocations: pd.DataFrame
    line_results: pd.DataFrame
    diagnostics: dict


def reconcile_cancellations(df, id_col='line_id'):
    """Strict-earlier FIFO ledger; raw events are never rewritten."""
    d=df.copy(); d['InvoiceDate']=pd.to_datetime(d.InvoiceDate); d['_id']=d[id_col].astype(str)
    d['_inv']=d.InvoiceNo.astype('string').str.strip(); d['_q']=pd.to_numeric(d.Quantity,errors='coerce')
    d['_p']=pd.to_numeric(d.UnitPrice,errors='coerce')
    d['_cancel']=d._inv.str.startswith('C',na=False)|d._q.lt(0)
    d['_disagree']=d._inv.str.startswith('C',na=False)^d._q.lt(0)
    # Timestamp then stable content id: cancellation can only consume already completed timestamp groups.
    d=d.sort_values(['InvoiceDate','_id'],kind='mergesort')
    inventory=defaultdict(deque); alloc=[]; results=[]
    for ts,group in d.groupby('InvoiceDate',sort=True):
        cancellations=group[group._cancel]
        for _,r in cancellations.iterrows():
            need=abs(float(r._q)) if pd.notna(r._q) else 0.; initial=need; reason=None
            if pd.isna(r.CustomerID): reason='missing_customer'
            else:
                key=(r.CustomerID,str(r.StockCode)); lots=inventory[key]
                price_exists=bool(lots)
                compatible=any(x[1]==r._p and x[2]>0 for x in lots)
                price_ever_seen=any(x[1]==r._p for x in lots)
                if price_exists and not price_ever_seen: reason='price_conflict'
                for lot in lots:
                    if need<=0: break
                    if lot[1]!=r._p or lot[2]<=0: continue
                    take=min(need,lot[2]); lot[2]-=take; need-=take
                    alloc.append({'cancellation_id':r._id,'positive_id':lot[0],'matched_quantity':take,
                                  'cancellation_time':ts,'positive_time':lot[3]})
                if need and reason is None: reason='insufficient_predecessor' if initial!=need else 'no_predecessor'
            results.append({'cancellation_id':r._id,'requested_quantity':initial,'matched_quantity':initial-need,
                            'unmatched_quantity':need,'status':'matched' if need==0 else ('partial' if need<initial else 'unmatched'),
                            'reason':reason,'indicator_disagreement':bool(r._disagree)})
        # Positives become eligible only after the entire equal-time group.
        for _,r in group[~group._cancel & group._q.gt(0) & group.CustomerID.notna()].iterrows():
            inventory[(r.CustomerID,str(r.StockCode))].append([r._id,r._p,float(r._q),ts])
    adf=pd.DataFrame(alloc,columns=['cancellation_id','positive_id','matched_quantity','cancellation_time','positive_time'])
    rdf=pd.DataFrame(results)
    total_req=float(rdf.requested_quantity.sum()) if len(rdf) else 0.; matched=float(rdf.matched_quantity.sum()) if len(rdf) else 0.
    counts=lambda col,val: int((rdf[col]==val).sum()) if len(rdf) else 0
    diag={'cancellation_like_lines':len(rdf),'matched_lines':counts('status','matched'),'partial_lines':counts('status','partial'),
          'unmatched_lines':counts('status','unmatched'),'matched_quantity':matched,'requested_quantity':total_req,
          'unmatched_quantity':total_req-matched,'matched_quantity_rate':matched/total_req if total_req else 0,
          'partial_rate':counts('status','partial')/len(rdf) if len(rdf) else 0,
          'conflict_rate':counts('reason','price_conflict')/len(rdf) if len(rdf) else 0,
          'unmatched_rate':counts('status','unmatched')/len(rdf) if len(rdf) else 0,
          'price_conflict_lines':counts('reason','price_conflict'),'missing_customer_lines':counts('reason','missing_customer'),
          'disagreement_lines':int(rdf.indicator_disagreement.sum()) if len(rdf) else 0,
          'quantity_conserved':bool(abs(matched-(float(adf.matched_quantity.sum()) if len(adf) else 0))<1e-9),
          'future_predecessor_violations':int((adf.positive_time>=adf.cancellation_time).sum()) if len(adf) else 0}
    return Reconciliation(adf,rdf,diag)


def asof_properties(queries, properties, *, strict=False, validate_result=None):
    """Order-invariant keyed property as-of expansion, preserving ambiguous states."""
    p=properties.copy(); q=queries.copy(); op='strict_lt' if strict else 'le'
    keys=['itemid','property','timestamp']
    grouped=[]
    for key,g in p.groupby(keys,dropna=False,sort=True):
        vals=sorted(set(g.value.astype(str)))
        grouped.append((*key, vals[0] if len(vals)==1 else None, len(vals)>1))
    updates=pd.DataFrame(grouped,columns=keys+['value','ambiguous'])
    properties_list=sorted(p.property.dropna().unique())
    rows=[]
    for _,r in q.sort_values('query_id',kind='mergesort').iterrows():
      for prop in properties_list:
        z=updates[(updates.itemid==r.itemid)&(updates.property==prop)]
        z=z[z.timestamp<r.timestamp] if strict else z[z.timestamp<=r.timestamp]
        if z.empty: pt=None; val=None; amb=False; missing=True
        else:
            u=z.loc[z.timestamp.idxmax()]; pt=u.timestamp; val=u.value; amb=bool(u.ambiguous); missing=amb
        rows.append({'query_id':r.query_id,'itemid':r.itemid,'property':prop,'query_timestamp':r.timestamp,
                     'property_timestamp':pt,'value':val,'ambiguous':amb,'missing':missing,'join_rule':op})
    out=pd.DataFrame(rows).sort_values(['query_id','property'],kind='mergesort').reset_index(drop=True)
    check=validate_result if validate_result is not None else out
    present=check.property_timestamp.notna()
    assert (check.loc[present,'itemid'].to_numpy()==check.loc[present,'itemid'].to_numpy()).all()
    if strict: assert (check.loc[present,'property_timestamp']<check.loc[present,'query_timestamp']).all()
    else: assert (check.loc[present,'property_timestamp']<=check.loc[present,'query_timestamp']).all()
    return out


@dataclass
class Episodes:
    episodes: pd.DataFrame
    diagnostics: dict


def build_next_event_episodes(events, validate_result=None):
    e=events.copy(); groups=[]
    for (v,t),g in e.groupby(['visitorid','timestamp'],sort=True):
        groups.append({'visitorid':v,'timestamp':t,'history_items':tuple(sorted(set(g.itemid))),
                       'event_types':tuple(sorted(g.event.astype(str))), 'target_item_group':None})
    gdf=pd.DataFrame(groups).sort_values(['visitorid','timestamp'],kind='mergesort')
    first=e.groupby('itemid').timestamp.min().to_dict(); rows=[]; censored=0
    for _,vg in gdf.groupby('visitorid',sort=True):
        recs=vg.to_dict('records')
        for i,r in enumerate(recs):
            if i+1==len(recs): censored+=1; continue
            nxt=recs[i+1]; target_items=tuple(sorted(nxt['history_items']))
            universe=tuple(sorted(k for k,v in first.items() if v<=r['timestamp']))
            contains=all(x in universe for x in target_items)
            rows.append({'visitorid':r['visitorid'],'timestamp':r['timestamp'],'target_timestamp':nxt['timestamp'],
              'history_items':r['history_items'],'target_items':target_items,'target_event_types':nxt['event_types'],
              'candidate_count':len(universe),'candidate_contains_target':contains,'scorable':contains})
    out=pd.DataFrame(rows).sort_values(['visitorid','timestamp'],kind='mergesort').reset_index(drop=True)
    check=validate_result if validate_result is not None else out
    if len(check):
        assert (check.target_timestamp>check.timestamp).all()
        assert check.loc[check.scorable,'candidate_contains_target'].all()
    cold=int((~out.scorable).sum()) if len(out) else 0
    violations=sum(any(first[x]>r.timestamp for x in first if first[x]<=r.timestamp) for r in out.itertuples())
    return Episodes(out,{'timestamp_groups':len(gdf),'evaluable_episodes':len(out),'right_censored_groups':censored,
      'cold_start_episodes':cold,'target_coverage':float(out.scorable.mean()) if len(out) else 0,
      'candidate_first_event_violations':int(violations)})


def canonical_manifest_bytes(manifest):
    return json.dumps(manifest,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()

def manifest_commitment(manifest): return hashlib.sha256(canonical_manifest_bytes(manifest)).hexdigest()
def verify_manifest_commitment(manifest, commitment): return manifest_commitment(manifest)==commitment.lower()

def check_horizon_completeness(task, cutoff=None, dataset_end=None, *, episodes_have_next=None, horizon_days=30):
    if task=='online': complete=pd.Timestamp(cutoff)+pd.Timedelta(days=horizon_days)<=pd.Timestamp(dataset_end)
    elif task=='retailrocket': complete=bool(episodes_have_next)
    else: raise ValueError('unknown task')
    return {'task':task,'complete':bool(complete)}

def holdout_governance_gate(manifest,state):
    failures=[]
    if not verify_manifest_commitment(manifest,state.get('commitment','')): failures.append('commitment_mismatch')
    if not state.get('owner') or state.get('owner')==state.get('builder'): failures.append('owner_not_independent')
    if not state.get('physical_custody_evidenced'): failures.append('physical_custody_not_evidenced')
    if len(state.get('reveals',[]))>1: failures.append('multiple_reveals')
    if state.get('reveals') and state.get('post_reveal_changes'): failures.append('post_reveal_change_invalidates_run')
    return {'pass':not failures,'failures':failures,'custody_claimed_only_if_evidenced':True}
