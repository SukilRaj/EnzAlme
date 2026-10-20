"""Render saved evaluation evidence only; standard library, no fitting or inference."""
from pathlib import Path
import csv, json, math, statistics, hashlib
from html import escape
from collections import defaultdict

OUT = Path(__file__).resolve().parent
ROOT = OUT.parent
sources = {}
def read(name, kind='json'):
    p = ROOT / name
    sources[name] = hashlib.sha256(p.read_bytes()).hexdigest()
    if kind == 'csv':
        return list(csv.DictReader(p.read_text(encoding='utf-8-sig').splitlines()))
    return json.loads(p.read_text(encoding='utf-8-sig'))

charts = []
colors = ['#167d9a', '#dc8650', '#7059aa', '#269576']
def chart(name, title, note, labels, panels, source):
    """Horizontal bars with a true zero origin and independent labeled linear axes."""
    row = 30
    left = max(250, min(800, max(map(len, labels)) * 6.5))
    width = left + 1000
    height = 165 + row * len(labels)
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
         '<style>text{font-family:Arial,sans-serif;fill:#233249}.title{font-size:24px;font-weight:bold}.small{font-size:12px}</style>',
         f'<rect width="100%" height="100%" fill="#fff"/><text x="24" y="35" class="title">{escape(title)}</text>',
         f'<text x="24" y="60" class="small">{escape(note)}</text>']
    for i, label in enumerate(labels):
        y = 124 + row*i
        if i % 2 == 0:
            s.append(f'<rect x="20" y="{y-19}" width="{width-40}" height="30" fill="#f1f5f9"/>')
        s.append(f'<text x="26" y="{y}" class="small">{escape(label)}</text>')
    for j, (metric, values) in enumerate(panels):
        start = left+j*245
        vals = [v for v in values if math.isfinite(v)]
        lo, hi = min(0,min(vals)), max(0,max(vals))
        if lo == hi: hi = lo+1
        scale = lambda v: start+175*(v-lo)/(hi-lo)
        zero = scale(0)
        s.append(f'<text x="{start}" y="88" font-size="14" font-weight="bold">{escape(metric)}</text>')
        s.append(f'<line x1="{zero}" x2="{zero}" y1="101" y2="{height-50}" stroke="#a9b6c4"/>')
        for i, v in enumerate(values):
            y = 124+row*i
            if math.isfinite(v):
                x = scale(v)
                s.append(f'<rect x="{min(x,zero)}" y="{y-14}" width="{max(1,abs(x-zero))}" height="16" rx="2" fill="{colors[j%4]}"/>')
                value = f'{v:,.3f}'
            else: value = 'undefined'
            s.append(f'<text x="{start+180}" y="{y}" font-size="11">{value}</text>')
        s.append(f'<text x="{start}" y="{height-29}" class="small">Axis: {lo:,.2f} to {hi:,.2f}</text>')
    s.append(f'<text x="24" y="{height-8}" class="small">Source: {escape(source)}</text></svg>')
    (OUT / (name+'.svg')).write_text(''.join(s),encoding='utf-8')
    charts.append((name+'.svg',title,note))

metrics = [('MAE (µM) ↓','mae'),('RMSE (µM) ↓','rmse'),('R² ↑','r2'),('Spearman ρ ↑','spearman')]
a = read('controlled_ablation_results.json')['aggregated_results']
labels = ['A · Conditions only', 'B · ESM-2 only', 'C · ESM-2 + conditions']
chart('01_ablation','Controlled feature ablation · confirmed 221 rows',
      'Unweighted mean of five protein-group folds. B Spearman is defined in 4/5 folds. Bars are means, not confidence intervals.',labels,
      [(title,[a[k]['metrics'][m+'_um' if m in ('mae','rmse') else m]['mean'] for k in 'ABC']) for title,m in metrics], 'controlled_ablation_results.json')
folds = read('ablation_error_analysis/fold_metrics.csv','csv')
chart('02_ablation_folds','Ablation · individual held-out fold results','Same fixed protein-group folds across A/B/C; undefined correlation is retained.',
      [f"{r['configuration']} · Fold {r['fold']} · n={r['test_records']}" for r in folds],
      [(t,[float(r[m+'_um' if m in ('mae','rmse') else m] or 'nan') for r in folds]) for t,m in metrics], 'ablation_error_analysis/fold_metrics.csv')
pooled = read('ablation_error_analysis/pooled_metrics.csv','csv')
chart('03_pooled','Pooled out-of-fold evaluation · 221 predictions per configuration',
      'Metrics recomputed over all held-out rows in the saved analysis; these differ from the mean of fold metrics.',labels,
      [(t,[float(r[m+'_um' if m in ('mae','rmse') else m]) for r in pooled]) for t,m in metrics], 'ablation_error_analysis/pooled_metrics.csv')
sweep = read('model_comparison_results.csv','csv')
groups = defaultdict(list)
for r in sweep: groups[(r['model'],r['configuration'],r['pca_components'])].append(r)
def mean(rows,m):
    v = [float(r[m]) for r in rows if r[m] and math.isfinite(float(r[m]))]
    return statistics.mean(v) if v else float('nan')
chart('04_all_model_configurations',f'Model comparison · all {len(groups)} saved configurations',
      'Confirmed 221 rows; mean across protein-group folds (finite values only). Separate experiment from controlled A/B/C.',
      [f'{model} | {cfg} | PCA={pca}' for model,cfg,pca in groups],
      [(t,[mean(rows,m) for rows in groups.values()]) for t,m in metrics], 'model_comparison_results.csv')
balance = read('protein_balance_sensitivity.json')['comparisons']
rows = [(f"{r['model']} · {label}",r[key]) for r in balance for label,key in [('221 rows','full_dataset'),('82 rows','balanced_dataset')]]
chart('05_balance','Protein-balance sensitivity',
      'Fold means. The 82-row subset changes the test distribution; differences do not establish improved production performance.',
      [x[0] for x in rows],[(t,[r['mean_'+m] for _,r in rows]) for t,m in metrics], 'protein_balance_sensitivity.json')
legacy = read('cross_validation_results.json')['folds']
chart('06_legacy','Legacy served model · separately reported evaluation',
      '227 reported records. Exact training/evaluation row membership unresolved. NOT a confirmed 221-row comparison.',
      [f"Fold {r['fold']} · n={r['records']}" for r in legacy],[(t,[r[m] for r in legacy]) for t,m in metrics], 'cross_validation_results.json (saved rounded fold values)')
rep = read('repeated_condition_variability.csv','csv')
rep.sort(key=lambda r:float(r['target_range_uM']),reverse=True)
chart('07_repeated_conditions','Observed variability · identical modeled conditions',
      'All saved repeated-condition groups; other assay metadata can differ. These are observations, not prediction error bars.',
      [f"{r['protein_name']} | {r['temperature_c']} °C, pH {r['ph']}, {r['duration_hours']} h | n={r['record_count']}" for r in rep],
      [(t,[float(r[k] or 'nan') for r in rep]) for t,k in [('Minimum (µM)','target_min_uM'),('Maximum (µM)','target_max_uM'),('Range (µM)','target_range_uM'),('SD (µM)','target_std_uM')]], 'repeated_condition_variability.csv')
for filename,title in [('actual_vs_predicted.png','Actual versus predicted · A/B/C'),('per_protein_squared_error.png','Squared error contribution by protein')]:
    p = ROOT/'ablation_error_analysis'/filename
    sources[str(p.relative_to(ROOT))] = hashlib.sha256(p.read_bytes()).hexdigest()
    charts.append(('../ablation_error_analysis/'+filename,title,'Existing project plot; preserved without alteration.'))
intro = ('Saved-result gallery: no models were fitted and no predictions were invented. MAE/RMSE are in µM (lower is better); R² and Spearman are dimensionless (higher is better). Negative R² means performance below the corresponding test-target mean baseline. There is no classification accuracy percentage. Fold means and pooled metrics are different summaries. Bars show saved means or individual values; consult source reports for fold standard deviations. Legacy results remain separate because exact row membership is unresolved.')
html = '<!doctype html><html><meta charset="utf-8"><title>EnzAIme evaluation plots</title><style>body{font:16px Arial;background:#edf2f7;color:#233249;margin:32px}section{background:white;padding:24px;margin:24px 0;border-radius:12px;overflow:auto}img{max-width:100%;height:auto}p{line-height:1.6}a{color:#167d9a}</style><h1>EnzAIme · evaluation and error plots</h1><p>'+intro+'</p>'
md = '# EnzAIme evaluation and error plots\n\n'+intro+'\n\n'
for filename,title,note in charts:
    html += f'<section><h2>{escape(title)}</h2><p>{escape(note)}</p><a href="{filename}">Open full-size figure</a><br><img src="{filename}" alt="{escape(title)}"></section>'
    md += f'- [{title}]({filename}) — {note}\n'
(OUT/'index.html').write_text(html+'</html>',encoding='utf-8')
(OUT/'README.md').write_text(md+'\nSource hashes are recorded in `source_manifest.json`. Rebuild with `python build_gallery.py` (standard library only). Existing datasets, reports and models are read-only inputs.\n',encoding='utf-8')
(OUT/'source_manifest.json').write_text(json.dumps(sources,indent=2),encoding='utf-8')
assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in sources.items())
import xml.etree.ElementTree as ET
for p in OUT.glob('*.svg'): ET.parse(p)
print(f'Validated {len(charts)} figures; {len(groups)} configurations; all {len(sources)} source hashes unchanged.')
