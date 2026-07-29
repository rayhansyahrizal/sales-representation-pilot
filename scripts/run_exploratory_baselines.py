#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,pathlib,subprocess,sys,time
import duckdb,numpy as np,pandas as pd
from sklearn.metrics import accuracy_score,log_loss,recall_score
ROOT=pathlib.Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'src'))
from sales_representation_audit.baselines import fit_online,bootstrap_customer_delta,ranking_metrics,append_ledger
from sales_representation_audit.exploratory import FEATURES,validate_availability
OUT=ROOT/'artifacts/exploratory'; SEED=20260729
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def event_eval(dev,ev,target='target_event'):
 classes=sorted(set(dev[target])|set(ev[target])); prior=dev[target].value_counts().reindex(classes,fill_value=0).to_numpy()+1; prior=prior/prior.sum()
 tab=pd.crosstab(dev.last_event,dev[target]).reindex(columns=classes,fill_value=0)+1
 probs=[]
 for x in ev.last_event:
  probs.append((tab.loc[x].to_numpy()/tab.loc[x].sum()) if x in tab.index else prior)
 probs=np.asarray(probs); pred=np.array(classes)[probs.argmax(1)]; global_pred=classes[int(prior.argmax())]; gp=np.tile(prior,(len(ev),1))
 return {'global':{'accuracy':float(np.mean(ev[target]==global_pred)),'macro_log_loss':float(log_loss(ev[target],gp,labels=classes))},'transition':{'accuracy':float(accuracy_score(ev[target],pred)),'macro_log_loss':float(log_loss(ev[target],probs,labels=classes)),'per_class_recall':{c:float(v) for c,v in zip(classes,recall_score(ev[target],pred,labels=classes,average=None,zero_division=0))}}}
def main():
 started=time.time(); manifest_path=ROOT/'manifests/exploratory-baseline-manifest.json'; manifest=json.loads(manifest_path.read_text()); mh=hashlib.sha256(json.dumps(manifest,sort_keys=True,separators=(',',':')).encode()).hexdigest(); validate_availability(FEATURES)
 con=duckdb.connect(); online=con.execute(f"select * from read_parquet('{OUT/'features/online_customer_episodes.parquet'}')").df(); rr=con.execute(f"select * from read_parquet('{OUT/'features/retailrocket_episodes.parquet'}')").df(); con.close()
 final=online.cutoff.max(); dev=online[online.cutoff<final]; ev=online[online.cutoff==final].reset_index(drop=True); o=fit_online(dev,ev,FEATURES,SEED); p,p0=o.pop('predictions'); o['bootstrap']=bootstrap_customer_delta(ev,p,p0,2000,SEED); o['development_rows']=len(dev); o['evaluation_rows']=len(ev); o['evaluation_cutoff']=pd.Timestamp(final).isoformat()
 boundary=int(rr.timestamp.quantile(.8,interpolation='lower')); rd=rr[rr.timestamp<=boundary]; re=rr[rr.timestamp>boundary]; r=event_eval(rd,re)
 rng=np.random.default_rng(SEED); perm=rd.copy(); perm['target_event']=rng.permutation(perm.target_event.to_numpy()); r['permuted_transition']=event_eval(perm,re)['transition']
 top10=[int(x) for x in rd.target_item.value_counts().head(10).index]; covered=re[re.covered]; r['items']={'bounded_compromise':'fixed development top-10 popularity; no full item scoring','top10':top10,**ranking_metrics(covered.target_item,top10),'candidate_coverage':float(re.covered.mean()),'cold_start_rate':float((~re.covered).mean()),'covered_episodes':len(covered),'all_evaluation_episodes':len(re)}; r['boundary_unix_ms']=boundary; r['development_rows']=len(rd); r['evaluation_rows']=len(re)
 online_gain=o['logistic']['pr_auc']-o['prevalence']['pr_auc']
 rr_gain=r['transition']['accuracy']-r['global']['accuracy']
 online_qualifies=online_gain>=.02 and o['bootstrap']['pr_auc_delta_ci95'][0]>0
 rr_qualifies=rr_gain>=.02
 # The control is task-specific: permutation must remove the gain of the task that qualifies.
 online_perm_gain=o['permuted']['pr_auc']-o['prevalence']['pr_auc']
 rr_perm_gain=r['permuted_transition']['accuracy']-r['global']['accuracy']
 perm_ok=(not online_qualifies or (online_perm_gain<online_gain/2 and o['permuted']['roc_auc']<.55)) and (not rr_qualifies or rr_perm_gain<rr_gain/2)
 technically=len(ev)>0 and len(re)>0
 proceed=technically and perm_ok and (online_qualifies or rr_qualifies); decision='PROCEED' if proceed else 'STOP'
 results={'label':'EXPLORATORY — builder-accessible evaluation data','decision':decision,'kill_rule_inputs':{'online_pr_auc_gain':online_gain,'retailrocket_accuracy_gain':rr_gain,'permutation_control_pass':bool(perm_ok),'both_technically_evaluable':bool(technically)},'online_retail_ii':o,'retailrocket':r,'manifest_hash':mh,'seed':SEED,'runtime_seconds':time.time()-started}
 rp=OUT/'results.json'; rp.write_text(json.dumps(results,indent=2,sort_keys=True)+'\n')
 run={'label':results['label'],'manifest_hash':mh,'base_commit':manifest['base_commit'],'git_sha':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'seed':SEED,'command':'uv run python scripts/run_exploratory_baselines.py','status':'complete','runtime_seconds':results['runtime_seconds'],'output_hashes':{'artifacts/exploratory/results.json':sha(rp)}}; (OUT/'run-manifest.json').write_text(json.dumps(run,indent=2,sort_keys=True)+'\n'); append_ledger(OUT/'run-ledger.jsonl',run)
 report=f"""# Lean exploratory baseline result\n\n**{results['label']}**\n\n## Mechanical decision: {decision}\n\nFrozen kill-rule inputs: Online logistic PR-AUC gain `{online_gain:.6f}` (95% customer-bootstrap delta CI `{o['bootstrap']['pr_auc_delta_ci95']}`); Retailrocket transition accuracy gain `{rr_gain:.6f}`; permutation control pass `{perm_ok}`; both datasets technically evaluable `{technically}`.\n\nOnline evaluation at `{o['evaluation_cutoff']}` had {len(ev):,} customer episodes. Logistic PR-AUC was `{o['logistic']['pr_auc']:.6f}` versus prevalence `{o['prevalence']['pr_auc']:.6f}`. Retailrocket evaluated {len(re):,} chronological episodes; transition accuracy was `{r['transition']['accuracy']:.6f}` versus global `{r['global']['accuracy']:.6f}`. Candidate coverage was `{r['items']['candidate_coverage']:.6f}` and fixed development-popularity Recall@10 was `{r['items']['recall_at_10']:.6f}`.\n\nNext-item ranking uses the preregistered bounded compromise: deterministic development-only top-10 popularity on covered episodes, not a full item scorer. These are hypothesis-generating builder-accessible results, not hidden-holdout or confirmatory evidence.\n"""; (OUT/'report.md').write_text(report); print(json.dumps(results,indent=2))
if __name__=='__main__': main()
