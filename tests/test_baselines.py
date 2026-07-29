import numpy as np
from sales_representation_audit.baselines import binary_metrics, ranking_metrics

def test_metrics():
 m=binary_metrics([0,1],[.1,.9]); assert m['pr_auc']==1 and m['roc_auc']==1
 r=ranking_metrics([2,9],[1,2,3]); assert r['recall_at_10']==.5 and r['ndcg_at_10']>0
