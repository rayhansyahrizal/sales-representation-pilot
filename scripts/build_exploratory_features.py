#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,pathlib,sys,time
import duckdb,pandas as pd
ROOT=pathlib.Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'src'))
from sales_representation_audit.exploratory import build_online_customer_episodes,build_retailrocket_episodes
OUT=ROOT/'artifacts/exploratory/features'; OUT.mkdir(parents=True,exist_ok=True)
def parquet(df,path):
 c=duckdb.connect(); c.register('x',df); c.execute(f"COPY x TO '{path}' (FORMAT PARQUET, COMPRESSION ZSTD)"); c.close()
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 timings={}; t=time.perf_counter()
 sheets=pd.read_excel(ROOT/'data/raw/online_retail_ii/online_retail_II.xlsx',sheet_name=None,engine='openpyxl')
 d=pd.concat(sheets.values(),ignore_index=True).rename(columns={'Invoice':'InvoiceNo','Price':'UnitPrice','Customer ID':'CustomerID'})
 d.InvoiceDate=pd.to_datetime(d.InvoiceDate); start=d.InvoiceDate.min().to_period('M').to_timestamp()+pd.offsets.MonthBegin(1); end=d.InvoiceDate.max()-pd.Timedelta(days=30)
 cutoffs=pd.date_range(start,end,freq='MS'); online=build_online_customer_episodes(d,cutoffs); op=OUT/'online_customer_episodes.parquet'; parquet(online,op); timings['online_seconds']=time.perf_counter()-t
 t=time.perf_counter(); ev=pd.read_csv(ROOT/'data/raw/retailrocket/events.csv',usecols=['visitorid','timestamp','itemid','event']); rr=build_retailrocket_episodes(ev); rp=OUT/'retailrocket_episodes.parquet'; parquet(rr,rp); timings['retailrocket_seconds']=time.perf_counter()-t
 summary={'label':'EXPLORATORY — builder-accessible evaluation data','online_rows':len(online),'online_cutoffs':len(cutoffs),'retailrocket_rows':len(rr),'timings_seconds':timings,'hashes':{str(op.relative_to(ROOT)):sha(op),str(rp.relative_to(ROOT)):sha(rp)}}
 (OUT.parent/'feature-build.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n'); print(json.dumps(summary,indent=2))
if __name__=='__main__': main()
