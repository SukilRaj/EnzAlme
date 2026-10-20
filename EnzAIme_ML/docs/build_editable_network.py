"""Native diagrams.net shapes only: no SVG/image-backed components."""
from pathlib import Path
import xml.etree.ElementTree as E

OUT=Path(__file__).parent/'EnzAIme_Editable_Network_Architecture.drawio'
doc=E.Element('mxfile',host='app.diagrams.net',version='24.7.17',type='device')
counter=0
def page(name):
    global root
    d=E.SubElement(doc,'diagram',name=name,id=name[:2])
    m=E.SubElement(d,'mxGraphModel',grid='1',gridSize='10',guides='1',connect='1',arrows='1',fold='1',page='1',pageScale='1',pageWidth='1840',pageHeight='1180',background='#FFFFFF')
    root=E.SubElement(m,'root')
    E.SubElement(root,'mxCell',id='0');E.SubElement(root,'mxCell',id='1',parent='0')
def box(label,x,y,w,h,fill='#ffffff',stroke='#53657b',size=18,parent='1',extra=''):
    global counter
    counter+=1
    ident=f'n{counter}'
    c=E.SubElement(root,'mxCell',id=ident,value=label,vertex='1',parent=parent,style=f'rounded=0;whiteSpace=wrap;html=0;fillColor={fill};strokeColor={stroke};strokeWidth=1.4;fontFamily=Arial;fontSize={size};fontColor=#183047;spacing=8;{extra}')
    E.SubElement(c,'mxGeometry',x=str(x),y=str(y),width=str(w),height=str(h),attrib={'as':'geometry'})
    return ident
def txt(label,x,y,w,h=35,size=18,color='#183047',bold=False,parent='1'):
    return box(label,x,y,w,h,'none','none',size,parent,f'align=left;spacing=0;fontColor={color};fontStyle={int(bold)};')
def edge(a,b,label='',color='#53657b',points=None,extra=''):
    global counter
    counter+=1
    c=E.SubElement(root,'mxCell',id=f'e{counter}',value=label,edge='1',parent='1',source=a,target=b,style=f'edgeStyle=orthogonalEdgeStyle;rounded=0;html=0;endArrow=block;endFill=1;strokeWidth=1.8;strokeColor={color};fontFamily=Arial;fontSize=15;labelBackgroundColor=#FFFFFF;{extra}')
    g=E.SubElement(c,'mxGeometry',relative='1',attrib={'as':'geometry'})
    if points:
        ar=E.SubElement(g,'Array',attrib={'as':'points'})
        for x,y in points:E.SubElement(ar,'mxPoint',x=str(x),y=str(y))
def tensor(parent,x=22,y=62,kind='matrix',color='#32889c'):
    # Every miniature cell is independently editable; parent group moves as one.
    if kind=='network':
        for i in range(3):
            box('',x+10*i,y+8*(2-i),82,38,'#e4edf8',color,12,parent)
        return
    rows,cols=(3,7) if kind=='matrix' else (1,9)
    for r in range(rows):
        for c in range(cols):box('',x+c*15,y+r*15,12,12,'#cde4ee' if (r+c)%2 else '#e9f2f7',color,10,parent)
def node(title,detail,x,y,w=260,h=172,fill='#eff6fa',kind='matrix'):
    group=box('',x,y,w,h,fill,'#7795a9',18,extra='container=1;collapsible=0;recursiveResize=0;')
    txt(title,16,12,w-30,42,20,bold=True,parent=group)
    tensor(group,kind=kind)
    txt(detail,16,121,w-30,42,16,parent=group)
    return group

page('01 Network architecture')
txt('EnzAIme: sequence-to-TPA prediction architecture',55,25,1720,55,30,bold=True)
txt('Served legacy research model  |  Single request: batch size = 1  |  Dimensions shown at each operation',55,85,1700,30,18)
txt('L = number of input residues; ℓ = token count after special tokens and truncation (ℓ ≤ 1,024). No convolution layers are used.',55,120,1740,28,17)
xs=[55,405,755,1105,1455]
seq=node('Protein sequence','s ∈ amino-acid alphabetᴸ',xs[0],195,kind='vector')
tok=node('ESM tokenizer','IDs + attention mask: 1 × ℓ',xs[1],195)
emb=node('Token embedding','Vocabulary 33; hidden size 1,280',xs[2],195)
enc=node('Frozen ESM-2','33 blocks; output 1 × ℓ × 1,280',xs[3],195,fill='#e9effb',kind='network')
pool=node('Masked mean pooling','Pool token axis → 1 × 1,280',xs[4],195,kind='vector')
for a,b,label in [(seq,tok,'L residues'),(tok,emb,'1 × ℓ'),(emb,enc,'1 × ℓ × 1,280'),(enc,pool,'1 × ℓ × 1,280')]:edge(a,b,label,extra='exitX=1;exitY=0.5;entryX=0;entryY=0.5;')
txt('FROZEN REPRESENTATION → SAVED REGRESSION PIPELINE',55,437,1300,28,18,bold=True)
vec=node('Protein vector','b ∈ ℝ¹²⁸⁰; float32',xs[0],490,kind='vector')
pca=node('Saved PCA','1,280 → 10 components',xs[1],490,kind='vector')
fuse=node('Feature concatenation','10 protein + 3 assay features',xs[2],490,fill='#f0f5e8',kind='vector')
scale=node('Saved StandardScaler','Scale all 13 fused features',xs[3],490,fill='#f0f5e8',kind='vector')
ridge=node('Saved Ridge regressor','α = 10; ẑ = β₀ + βᵀx',xs[4],490,fill='#fff3df',kind='network')
edge(pool,vec,'',points=[(1585,410),(185,410)],extra='exitX=0.5;exitY=1;entryX=0.5;entryY=0;')
for a,b,label in [(vec,pca,'1 × 1,280'),(pca,fuse,'1 × 10'),(fuse,scale,'1 × 13'),(scale,ridge,'1 × 13')]:edge(a,b,label,extra='exitX=1;exitY=0.5;entryX=0;entryY=0.5;')
conditions=box('Assay conditions\ne = [temperature °C, pH, duration h]\nShape: 1 × 3',700,738,370,95,'#f0f5e8','#78945a',18)
edge(conditions,fuse,'',extra='exitX=0.5;exitY=0;entryX=0.5;entryY=1;')
out=box('Predicted TPA concentration\nŷ = max(0, exp(ẑ) − 1)\nOutput: one scalar in µM (1 × 1)',1390,760,390,110,'#fff3df','#bf913d',20)
edge(ridge,out,'ẑ: one log-scale value',extra='exitX=0.5;exitY=1;entryX=0.5;entryY=0;')
txt('ESM-2 BLOCK DETAIL  (repeated 33 times)',55,715,625,30,18,bold=True)
b1=box('LayerNorm\n1,280',55,765,140,80,'#e9effb',size=16)
b2=box('Self-attention\n20 heads × 64\nRotary positions',230,765,165,80,'#e9effb',size=16)
b3=box('Residual add\n1,280',430,765,140,80,'#e9effb',size=16)
b4=box('LayerNorm\n1,280',55,905,140,80,'#e9effb',size=16)
b5=box('Feed-forward + GELU\n1,280 → 5,120 → 1,280',230,905,230,80,'#e9effb',size=16)
b6=box('Residual add\n1,280',495,905,140,80,'#e9effb',size=16)
edge(b1,b2);edge(b2,b3);edge(b3,b4,points=[(605,875),(125,875)])
edge(b4,b5);edge(b5,b6)
txt('Residual connections use each sublayer input. Final encoder LayerNorm precedes last_hidden_state.',700,920,1040,60,17)
txt('Pooling follows the attention mask, including special tokens. The masked-language-model head and ESMFold are not used.',700,990,1040,60,17)
box('MODEL STATUS: Legacy metadata reports 227 records. Exact training/evaluation row membership is unresolved.\nThis saved predictor is not established as trained on the confirmed 221-row research dataset.',55,1080,1725,65,'#fff9ed','#bfa576',17)

page('02 System and research flow')
txt('EnzAIme: application, evidence and controlled research',55,25,1730,55,29,bold=True)
txt('Native draw.io objects • drag a block to move it; double-click text to edit; connectors stay attached.',55,88,1730,30,17)
txt('APPLICATION / INFERENCE',55,150,1600,35,21,bold=True)
ui=box('Responsive React interface\nSequence input • assay conditions\nPrediction • candidate exploration',55,215,350,130,'#eaf4f6',size=20)
api=box('FastAPI\n/predict • /recommend\n/evaluation • /cross-validation',490,215,350,130,'#eaf4f6',size=20)
legacy=box('Legacy prediction pipeline\nESM-2 / cached vector → PCA\nFeature fusion → scaler → Ridge\nSee page 01 for dimensions',925,215,380,130,'#fff3df',size=19)
results=box('API response → UI\nTPA concentration (µM)\nRanked proteins + evidence counts\nLegacy model and lineage disclosure',1390,215,390,130,'#eaf4f6',size=19)
edge(ui,api,'request');edge(api,legacy,'conditions / sequence');edge(legacy,results,'prediction / scores')
confirm=box('Confirmed TPA/PET evidence\n221 records • 25 protein/sequence pairs\nUsed for recommendation counts and provenance',490,425,480,110,'#edf6ea','#729064',19)
cache=box('Saved model artifacts + embedding index\nPCA: 1,280 → 10; scaler: 13; Ridge: 13 → 1\nRecommendation vectors are reused from cache',1120,425,590,110,'#fff3df','#bfa576',18)
edge(confirm,api,'evidence only',extra='exitX=0.25;exitY=0;entryX=0.5;entryY=1;')
edge(cache,legacy,'read-only artifacts',extra='exitX=0.2;exitY=0;entryX=0.7;entryY=1;')
txt('Recommendations require conditions only. The same 25 proteins are scored; confirmed evidence does not establish model training membership.',55,565,1725,45,18)
txt('CONTROLLED RESEARCH / SEPARATE FROM THE SERVED ARTIFACT',55,640,1725,35,21,bold=True)
data=box('Provenance audit\n227 source assay rows\n221 confirmed + 6 ambiguous excluded',55,705,350,105,'#edf6ea',size=18)
fold=box('Shared 5-fold GroupKFold\nGroup by protein ID\nFit transforms only on training folds',490,705,380,105,'#eeebf7',size=18)
evaln=box('Held-out evaluation\nMAE • RMSE • R² • Spearman\nFold summaries and pooled OOF\nProtein / record error analysis',1390,705,390,240,'#eeebf7',size=20)
edge(data,fold,'221 rows')
branches=[]
for y,title in [(690,'A: environment [3] → scale → Ridge'),(780,'B: embedding [1,280] → scale → PCA [10] → Ridge'),(870,'C: embedding → scale → PCA [10]\n+ conditions [3] → scale [13] → Ridge')]:
    n=box(title,940,y,385,75,'#eeebf7','#8d81ad',17)
    branches.append(n);edge(fold,n,'',extra='exitX=1;exitY=0.5;entryX=0;entryY=0.5;');edge(n,evaln,'',extra='exitX=1;exitY=0.5;entryX=0;entryY=0.5;')
txt('All research branches: Ridge α = 10; log1p target; expm1 output. Research predictions are not clipped at zero.',55,970,1725,35,18)
box('SUPPORTING / FUTURE WORK\nImplemented: FireProtDB record extraction via UniProt mapping.\nProposed: mutation scoring and structure validation; neither is part of the served prediction network.',55,1040,1725,95,'#f7f8fa','#9ba5b2',18,extra='dashed=1;')
E.indent(doc)
E.ElementTree(doc).write(OUT,encoding='utf-8',xml_declaration=True)
tree=E.parse(OUT)
for d in tree.findall('diagram'):
    cells=d.findall('.//mxCell');ids={c.get('id') for c in cells}
    assert len(ids)==len(cells)
    assert not any('shape=image' in c.get('style','') for c in cells)
    for c in cells:
        if c.get('edge')=='1':assert c.get('source') in ids and c.get('target') in ids
print(f'Validated 2 pages, {counter} native editable objects; no embedded images: {OUT}')
