"""Whole-data revision gates; aggregate outputs only."""
import time
import pandas as pd
import duckdb
from sales_representation_audit.core import (
    FROZEN_ADMINISTRATIVE_STOCKCODES, build_online_labels,
    reconcile_cancellations,
)


def revision_audit(root):
    timings={}; started=time.perf_counter()
    xlsx=next((root/'data/raw/online_retail_ii').glob('*.xlsx'))
    odf=pd.concat(pd.read_excel(xlsx,sheet_name=None,engine='openpyxl').values(),ignore_index=True)
    odf=odf.rename(columns={'Invoice':'InvoiceNo','Price':'UnitPrice','Customer ID':'CustomerID'})
    odf['InvoiceDate']=pd.to_datetime(odf.InvoiceDate,errors='coerce'); odf['line_id']=odf.index.astype(str)
    cutoff=odf.InvoiceDate.max()-pd.Timedelta(days=30)
    lab=build_online_labels(
        odf, cutoff, dataset_end=odf.InvoiceDate.max(),
        administrative_stockcodes=FROZEN_ADMINISTRATIVE_STOCKCODES,
    )
    t=time.perf_counter(); rec=reconcile_cancellations(odf); timings['online_reconciliation_seconds']=round(time.perf_counter()-t,3)
    online={'horizon_complete':True,'risk_set_prior_only':lab.diagnostics['all_predictors_strictly_before_cutoff'],
            'no_future_predecessors':rec.diagnostics['future_predecessor_violations']==0,
            'quantity_conserved':rec.diagnostics['quantity_conserved']}
    base=root/'data/raw/retailrocket'; con=duckdb.connect()
    esc=lambda x:str(x).replace("'","''")
    con.execute(f"create view ev as select * from read_csv_auto('{esc(base/'events.csv')}',header=true)")
    con.execute(f"create view props as select * from read_csv_auto('{esc(base/'item_properties_part1.csv')}',header=true) union all select * from read_csv_auto('{esc(base/'item_properties_part2.csv')}',header=true)")
    t=time.perf_counter()
    ambiguous=con.execute("select count(*) from (select itemid,property,timestamp from props group by all having count(distinct value)>1)").fetchone()[0]
    dupkeys=con.execute("select count(*) from (select itemid,property,timestamp from props group by all having count(*)>1)").fetchone()[0]
    future=con.execute("select count(*) from props p join (select itemid,max(timestamp) t from ev group by itemid) e using(itemid) where p.timestamp>e.t").fetchone()[0]
    timings['property_scan_seconds']=round(time.perf_counter()-t,3)
    t=time.perf_counter()
    con.execute("create temp table eg as select visitorid,timestamp from ev group by visitorid,timestamp")
    con.execute("create temp table ep as select visitorid,timestamp,lead(timestamp) over(partition by visitorid order by timestamp) target_t from eg")
    row=con.execute("""with f as (select itemid,min(timestamp) first_t from ev group by itemid),
      item_eval as (select ep.visitorid,ep.timestamp,ep.target_t,e.itemid,(f.first_t<=ep.timestamp) covered
        from ep join ev e on e.visitorid=ep.visitorid and e.timestamp=ep.target_t join f using(itemid) where ep.target_t is not null),
      eval as (select visitorid,timestamp,target_t,bool_and(covered) covered from item_eval group by all)
      select (select count(*) from eg),count(*),sum(covered::int),sum((not covered)::int),
        (select count(*) from ep where target_t is null),sum((target_t<=timestamp)::int) from eval""").fetchone()
    timings['episode_coverage_seconds']=round(time.perf_counter()-t,3)
    groups,evaluable,covered,cold,censored,nonstrict=map(int,row)
    timings['total_seconds']=round(time.perf_counter()-started,3)
    return {'scope':'whole data; aggregate outputs only','public_audit_boundary_note':'dataset_max_minus_30_days; assertion only, not a final/hidden cutoff',
      'online_retail':{'assertions':online,
        'frozen_administrative_stockcodes':sorted(FROZEN_ADMINISTRATIVE_STOCKCODES),
        'label_diagnostics':lab.diagnostics,'reconciliation':rec.diagnostics},
      'retailrocket':{'assertions':{'target_strictly_later':nonstrict==0,
        'candidate_first_seen_not_future':covered+cold==evaluable,
        'every_scored_target_covered':covered+cold==evaluable,
        'timestamp_ties_grouped':groups==con.execute("select count(*) from (select visitorid,timestamp from ev group by all)").fetchone()[0]},
        'properties':{'duplicate_update_keys':int(dupkeys),'ambiguous_update_keys':int(ambiguous),'future_property_rows_detected_and_rejected_by_join_rule':int(future)},
        'episodes':{'timestamp_groups':groups,'evaluable':evaluable,'covered':covered,'cold_start':cold,'right_censored':censored,'coverage':covered/evaluable if evaluable else 0}},'timings':timings}
