import pandas as pd,numpy as np,json
from pathlib import Path
p=Path('.'); d=pd.read_csv('data/processed/tpa_pet_ml_confirmed.csv'); a=pd.read_csv('reports/results/controlled_ablation_results.csv'); m=pd.read_csv('master_dataset.csv'); idx=json.loads(Path('data/embeddings/index.json').read_text())
emb=[]
for x in d.protein_id.unique():
 v=np.load(Path('data/embeddings')/idx[str(x)]); emb.append(v.shape==(1280,) and bool(np.isfinite(v).all()))
stats={'records':len(d),'proteins':int(d.protein_id.nunique()),'master_records':len(m),'assays':sum(len(json.loads(x)) for x in m.activity_records_json),'zero_duration':int((d.duration_hours==0).sum()),'all_embeddings_valid':all(emb),'metrics':a.groupby('configuration')[['mae_um','rmse_um','r2','spearman']].mean().to_dict('index'),'folds':a[a.configuration=='A'][['fold','test_records','test_proteins']].to_dict('records'),'counts':d.groupby(['protein_id','protein_name']).size().sort_values(ascending=False).reset_index(name='records').to_dict('records'),'feature_counts':pd.read_csv('reports/results/feature_eligibility_audit.csv').eligibility.value_counts().to_dict()}
Path('.ppt_build/evidence.json').write_text(json.dumps(stats,indent=2),encoding='utf-8');print(json.dumps(stats,indent=2))
mc=json.loads(Path('reports/results/model_comparison_results.json').read_text()); print('comparison example',mc['summaries'][0])
