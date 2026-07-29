import pandas as pd
from sales_representation_audit.exploratory import build_online_customer_episodes, build_retailrocket_episodes

def test_online_strict_and_order_invariant():
 d=pd.DataFrame({'InvoiceNo':['1','2','3'],'StockCode':['A','A','A'],'Quantity':[1,1,1],'UnitPrice':[2,2,2],'CustomerID':[1,1,1],'InvoiceDate':pd.to_datetime(['2020-01-01','2020-02-02','2020-03-02'])})
 a=build_online_customer_episodes(d,[pd.Timestamp('2020-02-01')]); b=build_online_customer_episodes(d.sample(frac=1,random_state=1),[pd.Timestamp('2020-02-01')])
 pd.testing.assert_frame_equal(a,b); assert a.label.iloc[0]==1 and (a.feature_max_timestamp<a.cutoff).all()

def test_rr_strict_grouping():
 e=pd.DataFrame({'visitorid':[1,1,1,2],'timestamp':[1,1,2,1],'itemid':[2,1,3,4],'event':['view','view','transaction','view']})
 x=build_retailrocket_episodes(e); assert len(x)==1 and x.target_timestamp.iloc[0]>x.timestamp.iloc[0]
