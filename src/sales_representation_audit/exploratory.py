"""Leakage-safe builders for builder-accessible exploratory baselines."""
from __future__ import annotations
import pandas as pd
from .core import FROZEN_ADMINISTRATIVE_STOCKCODES, _valid_positive

FEATURES = ['recency_days','purchase_frequency','unique_invoices','unique_items','gross_quantity','gross_value','tenure_days','calendar_month']

def validate_availability(columns):
    forbidden={'future_purchase_count','target_event','target_item','target_timestamp'}
    bad=forbidden.intersection(columns)
    if bad: raise ValueError(f'future-derived feature rejected: {sorted(bad)}')
    return True

def build_online_customer_episodes(df, cutoffs, horizon_days=30):
    d=df.copy(); d['InvoiceDate']=pd.to_datetime(d.InvoiceDate)
    valid=d[_valid_positive(d,set(FROZEN_ADMINISTRATIVE_STOCKCODES))].copy()
    valid['Quantity']=pd.to_numeric(valid.Quantity); valid['UnitPrice']=pd.to_numeric(valid.UnitPrice)
    valid['value']=valid.Quantity*valid.UnitPrice
    rows=[]
    for cutoff in sorted(pd.Timestamp(x) for x in cutoffs):
        prior=valid[valid.InvoiceDate<cutoff]
        future=valid[(valid.InvoiceDate>=cutoff)&(valid.InvoiceDate<cutoff+pd.Timedelta(days=horizon_days))]
        pos=set(future.CustomerID.unique())
        g=prior.groupby('CustomerID',sort=True)
        a=g.agg(last=('InvoiceDate','max'),first=('InvoiceDate','min'),purchase_frequency=('InvoiceNo','nunique'),unique_invoices=('InvoiceNo','nunique'),unique_items=('StockCode','nunique'),gross_quantity=('Quantity','sum'),gross_value=('value','sum')).reset_index()
        a['recency_days']=(cutoff-a['last']).dt.total_seconds()/86400
        a['tenure_days']=(cutoff-a['first']).dt.total_seconds()/86400
        a['calendar_month']=cutoff.month; a['cutoff']=cutoff; a['feature_max_timestamp']=a['last']; a['label']=a.CustomerID.isin(pos).astype(int)
        rows.append(a[['CustomerID','cutoff','feature_max_timestamp','label']+FEATURES])
    out=pd.concat(rows,ignore_index=True)
    assert (out.feature_max_timestamp<out.cutoff).all()
    return out.sort_values(['cutoff','CustomerID'],kind='mergesort').reset_index(drop=True)

def build_retailrocket_episodes(events):
    e=events[['visitorid','timestamp','itemid','event']].copy()
    # Collapse simultaneous rows deterministically, choosing a stable representative target.
    g=(e.groupby(['visitorid','timestamp'],sort=True)
       .agg(itemid=('itemid','min'),event=('event','min')).reset_index()
       .sort_values(['visitorid','timestamp'],kind='mergesort'))
    by=g.groupby('visitorid',sort=False)
    g['target_timestamp']=by.timestamp.shift(-1); g['target_item']=by.itemid.shift(-1); g['target_event']=by.event.shift(-1)
    g['last_event']=by.event.shift(1).fillna('__START__')
    out=g[g.target_timestamp.notna()].copy()
    assert (out.target_timestamp>out.timestamp).all()
    first=e.groupby('itemid').timestamp.min()
    out['target_item']=out.target_item.astype('int64')
    out['covered']=out.target_item.map(first).le(out.timestamp)
    return out.reset_index(drop=True)
