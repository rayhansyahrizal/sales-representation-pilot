"""Simple deterministic exploratory baselines and metrics."""
from __future__ import annotations
import json, os
from pathlib import Path
import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score, brier_score_loss, log_loss, accuracy_score, recall_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

def binary_metrics(y,p):
    y=np.asarray(y); p=np.clip(np.asarray(p),1e-9,1-1e-9); n=max(1,int(np.ceil(len(y)*.1))); selected=np.argsort(-p)[:n]
    return {'pr_auc':float(average_precision_score(y,p)),'roc_auc':float(roc_auc_score(y,p)),'brier':float(brier_score_loss(y,p)),'log_loss':float(log_loss(y,p)),'precision_at_10pct':float(y[selected].mean()),'recall_at_10pct':float(y[selected].sum()/max(1,y.sum()))}

def bootstrap_customer_delta(df,p1,p0,n=2000,seed=20260729):
    ids=np.array(sorted(df.CustomerID.unique())); rng=np.random.default_rng(seed); vals=[]
    groups={x:np.flatnonzero(df.CustomerID.to_numpy()==x) for x in ids}
    for _ in range(n):
        chosen=rng.choice(ids,len(ids),replace=True); idx=np.concatenate([groups[x] for x in chosen])
        y=df.label.to_numpy()[idx]
        if len(np.unique(y))>1: vals.append(average_precision_score(y,np.asarray(p1)[idx])-average_precision_score(y,np.asarray(p0)[idx]))
    return {'resamples':n,'pr_auc_delta_ci95':[float(np.quantile(vals,.025)),float(np.quantile(vals,.975))]}

def fit_online(dev,ev,features,seed=20260729):
    validate=set(features)-set(dev.columns)
    if validate: raise ValueError(validate)
    model=make_pipeline(SimpleImputer(strategy='median'),StandardScaler(),LogisticRegression(C=1.0,max_iter=500,random_state=seed))
    model.fit(dev[features],dev.label); p=model.predict_proba(ev[features])[:,1]; prev=float(dev.label.mean()); p0=np.full(len(ev),prev)
    rng=np.random.default_rng(seed); yp=rng.permutation(dev.label.to_numpy()); perm=make_pipeline(SimpleImputer(strategy='median'),StandardScaler(),LogisticRegression(C=1.0,max_iter=500,random_state=seed)).fit(dev[features],yp).predict_proba(ev[features])[:,1]
    return {'prevalence':binary_metrics(ev.label,p0),'logistic':binary_metrics(ev.label,p),'permuted':binary_metrics(ev.label,perm),'predictions':(p,p0)}

def ranking_metrics(targets,top10):
    ranks={x:i+1 for i,x in enumerate(top10)}; rr=[ranks.get(int(x)) for x in targets]
    return {'recall_at_10':float(np.mean([r is not None for r in rr])),'ndcg_at_10':float(np.mean([0 if r is None else 1/np.log2(r+1) for r in rr]))}

def append_ledger(path,record):
    p=Path(path); p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('a') as f: f.write(json.dumps(record,sort_keys=True)+'\n'); f.flush(); os.fsync(f.fileno())
