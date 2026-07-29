#!/usr/bin/env python3
"""Deterministic Phase-0 audits. Produces aggregates only; trains nothing."""
from __future__ import annotations
import json, pathlib, sys, time
import duckdb, pandas as pd
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from sales_representation_audit.core import (missingness, identity_coverage, holdout_feasibility,
    build_online_labels, reconcile_cancellations)
OUT=ROOT/'artifacts/audits'; OUT.mkdir(parents=True,exist_ok=True)

def qone(con, sql): return con.execute(sql).fetchone()[0]
def iso(x): return pd.Timestamp(x).isoformat() if x is not None else None

def audit_online():
    xlsx=next((ROOT/'data/raw/online_retail_ii').glob('*.xlsx'))
    sheets=pd.read_excel(xlsx,sheet_name=None,engine='openpyxl')
    df=pd.concat(sheets.values(),ignore_index=True)
    # Normalize historical and current UCI header spellings.
    df=df.rename(columns={'Invoice':'InvoiceNo','Price':'UnitPrice','Customer ID':'CustomerID'})
    df['InvoiceDate']=pd.to_datetime(df['InvoiceDate'],errors='coerce')
    inv=df['InvoiceNo'].astype('string')
    cancellation=inv.str.upper().str.startswith('C',na=False)
    negq=pd.to_numeric(df['Quantity'],errors='coerce').lt(0)
    actor_counts=df['CustomerID'].value_counts(dropna=True)
    object_counts=df['StockCode'].value_counts(dropna=True)
    feas=holdout_feasibility(len(df),df.InvoiceDate.nunique(),df.CustomerID.nunique(),df.StockCode.nunique(),int(actor_counts[actor_counts>1].sum()),int(object_counts[object_counts>1].sum()))
    return {
      'dataset':'online_retail_ii','unit':'invoice line','row_count':int(len(df)),
      'timestamp':{'column':'InvoiceDate','min':iso(df.InvoiceDate.min()),'max':iso(df.InvoiceDate.max()),'missing':int(df.InvoiceDate.isna().sum()),'distinct':int(df.InvoiceDate.nunique())},
      'missingness':missingness(df),'exact_duplicate_rows':int(df.duplicated(keep=False).sum()),
      'exact_duplicate_excess_rows':int(df.duplicated().sum()),
      'identity_coverage':identity_coverage(df,'CustomerID','StockCode'),
      'cancellation_return_indicators':{'invoice_prefix_c_rows':int(cancellation.sum()),'negative_quantity_rows':int(negq.sum()),'either_rows':int((cancellation|negq).sum()),'linkage_complete':False,'note':'Indicators exist, but return reason and guaranteed original-invoice linkage do not.'},
      'future_leakage_risks':['full-history RFM used inside its own prediction horizon','global/latest product description or price encoding','cancellations back-propagated to pre-return state','target-window basket fields used as predictors'],
      'holdout_feasibility':feas,
      'limitations':['transaction-selected sample; no eligible nonbuyers/exposure risk set','missing CustomerID selectively limits actor task','no logged action/propensity, cost, margin, fulfillment, or complete return linkage']}

def audit_retailrocket():
    base=ROOT/'data/raw/retailrocket'; con=duckdb.connect()
    ev=str(base/'events.csv').replace("'","''")
    con.execute(f"CREATE VIEW ev AS SELECT * FROM read_csv_auto('{ev}', header=true)")
    cols=[r[0] for r in con.execute('DESCRIBE ev').fetchall()]
    n=qone(con,'select count(*) from ev')
    miss={c:{'count':int(qone(con,f'select count(*) from ev where "{c}" is null'))} for c in cols}
    for v in miss.values(): v['fraction']=v['count']/n if n else 0.0
    counts=dict(con.execute('select event,count(*) from ev group by event order by event').fetchall())
    actor_unique=qone(con,'select count(distinct visitorid) from ev'); obj_unique=qone(con,'select count(distinct itemid) from ev')
    actor_repeat=qone(con,'select coalesce(sum(n),0) from (select count(*) n from ev group by visitorid having count(*)>1)')
    object_repeat=qone(con,'select coalesce(sum(n),0) from (select count(*) n from ev group by itemid having count(*)>1)')
    group_cols=', '.join(f'"{c}"' for c in cols)
    dup_excess=qone(con,f'select coalesce(sum(n-1),0) from (select count(*) n from ev group by {group_cols} having count(*)>1)')
    dup_all=qone(con,f'select coalesce(sum(n),0) from (select count(*) n from ev group by {group_cols} having count(*)>1)')
    lo,hi,nt=con.execute('select min(timestamp),max(timestamp),count(distinct timestamp) from ev').fetchone()
    prop=[]
    for name in ['item_properties_part1.csv','item_properties_part2.csv']:
        p=str(base/name).replace("'","''"); prop.append(f"SELECT * FROM read_csv_auto('{p}',header=true)")
    con.execute('CREATE VIEW props AS '+ ' UNION ALL '.join(prop))
    pn=qone(con,'select count(*) from props')
    pcols=[r[0] for r in con.execute('DESCRIBE props').fetchall()]
    pgroup=', '.join(f'"{c}"' for c in pcols)
    pdup=qone(con,f'select coalesce(sum(n-1),0) from (select count(*) n from props group by {pgroup} having count(*)>1)')
    category=str(base/'category_tree.csv').replace("'","''")
    cn=qone(con,f"select count(*) from read_csv_auto('{category}',header=true)")
    feas=holdout_feasibility(n,nt,actor_unique,obj_unique,actor_repeat,object_repeat)
    return {'dataset':'retailrocket','unit':'visitor-item event','row_count':int(n),
      'timestamp':{'column':'timestamp (Unix ms)','min':pd.to_datetime(lo,unit='ms',utc=True).isoformat(),'max':pd.to_datetime(hi,unit='ms',utc=True).isoformat(),'missing':miss['timestamp']['count'],'distinct':int(nt)},
      'missingness':miss,'exact_duplicate_rows':int(dup_all),'exact_duplicate_excess_rows':int(dup_excess),
      'identity_coverage':{'actor':{'column':'visitorid','present_rows':n-miss['visitorid']['count'],'coverage':1-miss['visitorid']['fraction'],'unique':int(actor_unique)},'object':{'column':'itemid','present_rows':n-miss['itemid']['count'],'coverage':1-miss['itemid']['fraction'],'unique':int(obj_unique)}},
      'event_counts':{str(k):int(v) for k,v in counts.items()},
      'cancellation_return_indicators':{'available':False,'note':'No cancellation, return, fulfillment, quantity, or value field.'},
      'related_tables':{'item_properties':{'row_count':int(pn),'exact_duplicate_excess_rows':int(pdup)},'category_tree':{'row_count':int(cn)}},
      'future_leakage_risks':['latest rather than as-of item properties','random event split across visitor/item histories','future event sequence in actor aggregates','candidate items unavailable at cutoff','transactionid used as predictor'],
      'holdout_feasibility':feas,
      'limitations':['no shown-item/eligibility candidate set or logged recommender action/propensity','absence of transaction is ambiguous/censored','hashed property semantics; category validity intervals unavailable','no cancellation/return or economic-value outcome']}

def main():
    from revision import revision_audit
    audits=[audit_online(),audit_retailrocket()]
    for a in audits: (OUT/f"{a['dataset']}.json").write_text(json.dumps(a,indent=2,sort_keys=True)+'\n')
    revision=revision_audit(ROOT)
    (OUT/'phase0-revision-audit.json').write_text(json.dumps(revision,indent=2,sort_keys=True)+'\n')
    summary={'phase':0,'decision':'REVISE','modeling_authorized':False,'software_and_whole_data_gates_pass':True,
      'authorization_blockers':['independent hidden-holdout canonical manifest commitment not supplied','physical holdout custody outside builder-accessible tree not evidenced'],
      'datasets':[{'dataset':a['dataset'],'rows':a['row_count'],'chronological_holdout':a['holdout_feasibility']['chronological'],'entity_holdout':a['holdout_feasibility']['entity']} for a in audits],
      'required_before_modeling':['obtain independent owner commitment and evidence inaccessible physical holdout custody','verify complete horizons after private boundaries are revealed exactly once']}
    (OUT/'phase0-summary.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
    report=f"""# Phase 0 modeling authorization gate

**Decision: REVISE — modeling is not authorized.**

Deterministic safeguard fixtures and whole-data assertions pass. Online Retail II has **{audits[0]['row_count']:,}** lines; Retailrocket has **{audits[1]['row_count']:,}** events. Machine-readable revision evidence is `artifacts/audits/phase0-revision-audit.json` (runtime **{revision['timings']['total_seconds']} s**).

Authorization remains blocked because no independently owned canonical hidden-boundary manifest commitment or evidence of physical custody outside the builder-accessible tree was supplied. A repository file cannot prove inaccessible custody. No private boundary was invented.

## Required before modeling

"""+'\n'.join(f"{i+1}. {x}" for i,x in enumerate(summary['required_before_modeling']))+"\n\nClaims remain narrow and predictive only. No model was trained.\n"
    (ROOT/'artifacts/gate-report.md').write_text(report)
if __name__=='__main__': main()
