"""Generate editable draw.io architecture and a matching standalone SVG."""
from pathlib import Path
from html import escape
import base64
import xml.etree.ElementTree as ET

OUT = Path(__file__).resolve().parent
W, H = 1800, 1630
svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
       '<title>EnzAIme system architecture</title><desc>Confirmed data and frozen protein representations feed controlled research. A separate legacy model serves predictions and rankings with confirmed evidence. Mutation extraction exists; mutation and structure validation are proposed.</desc>',
       '<rect width="1800" height="1630" fill="#f5f7fc"/>']
mx = ET.Element('mxfile', host='app.diagrams.net', version='24.7.17')
diagram = ET.SubElement(mx, 'diagram', id='enzaime-architecture', name='EnzAIme architecture')
model = ET.SubElement(diagram, 'mxGraphModel', dx='1800', dy='1630', grid='1', gridSize='10', page='1', pageScale='1', pageWidth=str(W), pageHeight=str(H), background='#f5f7fc')
root = ET.SubElement(model,'root')
ET.SubElement(root,'mxCell',id='0')
ET.SubElement(root,'mxCell',id='1',parent='0')
serial=0

def cell(value, style, x,y,w,h):
    global serial
    serial+=1
    c=ET.SubElement(root,'mxCell',id=str(serial+1),value=value,style=style,vertex='1',parent='1')
    ET.SubElement(c,'mxGeometry',x=str(x),y=str(y),width=str(w),height=str(h),attrib={'as':'geometry'})
    return c.attrib['id']

def rect(x,y,w,h,fill,stroke='none',radius=18,dashed=False):
    svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{stroke}" stroke-width="1.5"'+(' stroke-dasharray="8 5"' if dashed else '')+'/>')
    return cell('',f'rounded=1;arcSize=12;fillColor={fill};strokeColor={stroke};strokeWidth=1.5;dashed={int(dashed)};',x,y,w,h)

def text(x,y,s,size=20,color='#26334b',weight=400,w=1550):
    svg.append(f'<text x="{x}" y="{y}" font-family="Arial, sans-serif" font-size="{size}" fill="{color}" font-weight="{weight}">{escape(s)}</text>')
    cell(s,f'text;html=0;align=left;verticalAlign=middle;whiteSpace=wrap;overflow=hidden;strokeColor=none;fillColor=none;fontFamily=Arial;fontSize={size};fontColor={color};fontStyle={1 if weight>=600 else 0};spacing=0;',x,y-size,w,size+7)

ICONS={
'database':'<ellipse cx="32" cy="13" rx="23" ry="9"/><path d="M9 13v36c0 12 46 12 46 0V13M9 29c0 12 46 12 46 0M9 43c0 12 46 12 46 0"/>',
'audit':'<rect x="13" y="8" width="36" height="48" rx="5"/><path d="M23 6h16v9H23zM21 29l4 4 8-9M36 28h7M21 44l4 4 8-9M36 43h7"/>',
'protein':'<path d="M12 9c44 0-4 46 40 46M52 9C8 9 56 55 12 55M18 15h28M23 24h18M23 40h18M18 49h28"/><circle cx="12" cy="9" r="3"/><circle cx="52" cy="55" r="3"/>',
'fusion':'<rect x="7" y="8" width="18" height="15" rx="3"/><rect x="7" y="41" width="18" height="15" rx="3"/><rect x="42" y="24" width="17" height="16" rx="3"/><path d="M25 16h7v16h10M25 48h7V32"/>',
'fold':'<rect x="7" y="8" width="50" height="48" rx="4"/><path d="M17 8v48M27 8v48M37 8v48M47 8v48M7 18h50M7 28h50M7 38h50M7 48h50"/>',
'model':'<circle cx="11" cy="15" r="5"/><circle cx="11" cy="48" r="5"/><circle cx="32" cy="12" r="5"/><circle cx="32" cy="32" r="5"/><circle cx="32" cy="52" r="5"/><circle cx="55" cy="32" r="6"/><path d="M16 15l11-3M16 15l11 17M16 48l11-16M16 48l11 4M37 12l12 20M37 32h12M37 52l12-20"/>',
'chart':'<path d="M10 7v48h48M19 43V30h8v13M33 43V20h8v23M47 43V10h8v33"/>',
'browser':'<rect x="5" y="9" width="54" height="40" rx="5"/><path d="M5 20h54M24 49v8h16v-8M16 57h32M12 14h2M20 14h2M28 14h2M14 29h18M14 37h12M40 29h10v12H40z"/>',
'api':'<rect x="7" y="5" width="50" height="16" rx="4"/><rect x="7" y="25" width="50" height="16" rx="4"/><path d="M15 13h2M15 33h2M27 13h21M27 33h21M32 41v14M14 55h36"/>',
'rank':'<path d="M8 16h11M8 32h11M8 48h11M27 12h30v8H27zM27 28h23v8H27zM27 44h16v8H27z"/>',
'molecule':'<path d="M15 15l29 3 8 29-26 8L9 35zM15 15l11 40M44 18L9 35M26 55l18-37"/><circle cx="15" cy="15" r="6"/><circle cx="44" cy="18" r="7"/><circle cx="52" cy="47" r="5"/><circle cx="26" cy="55" r="5"/><circle cx="9" cy="35" r="5"/>',
}
def icon(x,y,kind,color):
    body=f'<g fill="none" stroke="{color}" stroke-width="2.8" stroke-linecap="round" stroke-linejoin="round">{ICONS[kind]}</g>'
    svg.append(f'<svg x="{x}" y="{y}" width="58" height="58" viewBox="0 0 64 64">{body}</svg>')
    data=base64.b64encode(f'<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64">{body}</svg>'.encode()).decode()
    cell('',f'shape=image;imageAspect=0;aspect=fixed;image=data:image/svg+xml,{data};',x,y,58,58)

def arrow(points,color,label=None,dashed=False):
    path='M'+' L'.join(f'{x},{y}' for x,y in points)
    svg.append(f'<path d="{path}" fill="none" stroke="{color}" stroke-width="3"'+(' stroke-dasharray="8 6"' if dashed else '')+'/>')
    x,y=points[-1]; px,py=points[-2]
    if x>px: tip=f'{x},{y} {x-10},{y-6} {x-10},{y+6}'
    elif x<px: tip=f'{x},{y} {x+10},{y-6} {x+10},{y+6}'
    else: tip=f'{x},{y} {x-6},{y-10} {x+6},{y-10}'
    svg.append(f'<polygon points="{tip}" fill="{color}"/>')
    global serial
    serial+=1
    c=ET.SubElement(root,'mxCell',id=str(serial+1),value='',style=f'edgeStyle=none;endArrow=block;endFill=1;strokeColor={color};strokeWidth=3;dashed={int(dashed)};',edge='1',parent='1')
    g=ET.SubElement(c,'mxGeometry',relative='1',attrib={'as':'geometry'})
    for pt,role in [(points[0],'sourcePoint'),(points[-1],'targetPoint')]: ET.SubElement(g,'mxPoint',x=str(pt[0]),y=str(pt[1]),attrib={'as':role})
    if len(points)>2:
        a=ET.SubElement(g,'Array',attrib={'as':'points'})
        for px,py in points[1:-1]: ET.SubElement(a,'mxPoint',x=str(px),y=str(py))

def card(x,y,title,lines,kind,color,bg,w=375,h=188):
    rect(x,y,w,h,'#ffffff',bg)
    rect(x+18,y+18,72,72,bg,radius=16)
    icon(x+25,y+25,kind,color)
    for j,line in enumerate(title.split('|')): text(x+106,y+43+j*25,line,22,'#172b46',700,w-120)
    for j,line in enumerate(lines): text(x+22,y+119+j*25,line,18,'#42536b',400,w-38)

def lane(y,h,index,title,subtitle,color,bg):
    rect(35,y,1730,h,bg)
    rect(57,y+18,46,38,color,radius=11)
    text(68,y+45,index,20,'#ffffff',700,38)
    text(120,y+46,title,25,'#172b46',700,1550)
    text(120,y+74,subtitle,17,'#526179',400,1560)

rect(0,0,1800,151,'#122a43',radius=0)
text(65,59,'EnzAIme',43,'#ffffff',700)
text(65,103,'SYSTEM ARCHITECTURE  /  Environment-aware TPA prediction & protein exploration',23,'#c8e5ed')
icon(1665,43,'protein','#74e0d1')
xs=[65,495,925,1355]
lane(180,306,'01','DATA & PROTEIN REPRESENTATION','Implemented • provenance is retained from source evidence through candidate metadata','#087f8c','#e8f7f6')
card(xs[0],280,'Source evidence',['Legacy assay table: 227 rows','PAZy records + master mapping','Sequence, assay, units, DOI'],'database','#087f8c','#d3efeb')
card(xs[1],280,'Provenance|& construction',['Resolve TPA measurement identity','Standardize µM and hours','Flag duplicates and ambiguity'],'audit','#087f8c','#d3efeb')
card(xs[2],280,'Confirmed evidence',['221 records • 25 proteins','6 ambiguous records excluded','Sequence + conditions + target'],'database','#087f8c','#d3efeb')
card(xs[3],280,'Frozen ESM-2',['Sequence → 1,280-D vector','No encoder fine-tuning','Existing embeddings + index'],'protein','#087f8c','#d3efeb')
for i in range(3): arrow([(xs[i]+375,373),(xs[i+1],373)],'#087f8c')

lane(545,323,'02','CONTROLLED RESEARCH PIPELINE','Confirmed 221-row dataset + indexed embeddings • identical protein-grouped folds across A / B / C','#7553c7','#f0ecfb')
card(xs[0],645,'Feature blocks',['A  Environment: T, pH, time','B  Frozen protein embeddings','C  Embeddings + environment'],'fusion','#7553c7','#e5dcf8')
card(xs[1],645,'Fold preparation',['5-fold GroupKFold by protein','Train/test protein sets disjoint','Shared splits for A, B and C'],'fold','#7553c7','#e5dcf8')
card(xs[2],645,'Controlled prediction',['Train-fold scaling + PCA*','Ridge α = 10 • log1p target','Held-out predictions → µM'],'model','#7553c7','#e5dcf8')
card(xs[3],645,'Evaluation & errors',['MAE • RMSE • R² • Spearman','Mean-fold + pooled OOF metrics','Per-protein and source audits'],'chart','#7553c7','#e5dcf8')
for i in range(3): arrow([(xs[i]+375,738),(xs[i+1],738)],'#7553c7')
arrow([(1540,468),(1540,516),(253,516),(253,545)],'#7553c7')
rect(620,495,580,36,'#f5f7fc',radius=8)
text(637,520,'Confirmed conditions + targets and frozen embeddings',17,'#7553c7',600,560)
text(91,852,'* PCA: 10 components for B/C; all learned preprocessing is fitted within training folds.',16,'#63567f')

lane(935,333,'03','LIVE APPLICATION & LEGACY MODEL','Implemented • evidence comes from confirmed records; scores come from the existing legacy artifacts','#c17a13','#fff4df')
card(xs[0],1035,'Responsive React UI',['Sequence + assay conditions','Candidate exploration by conditions','Loading, validation, error states'],'browser','#c17a13','#ffebc3',h=195)
card(xs[1],1035,'FastAPI services',['POST /predict • POST /recommend','GET /evaluation • /cross-validation','Confirmed evidence counts'],'api','#c17a13','#ffebc3',h=195)
card(xs[2],1035,'Legacy research|predictor',['Saved PCA + scaler + Ridge','Predict: fresh ESM-2 embedding','Recommend: cached embeddings'],'model','#c17a13','#ffebc3',h=195)
card(xs[3],1035,'Results & disclosure',['Predicted TPA in µM • ranked list','Confirmed evidence + provenance','Legacy labels on scores/metrics'],'rank','#c17a13','#ffebc3',h=195)
for i in range(3): arrow([(xs[i]+375,1128),(xs[i+1],1128)],'#c17a13')
text(89,1251,'Legacy metadata reports 227 records. Exact training/evaluation row membership is unresolved.',17,'#875e22',600)
text(66,906,'Research results are reported separately; the controlled experiments do not replace the served artifacts.',18,'#5a6780',600)

lane(1305,248,'04','MUTATION & STRUCTURE EXTENSION','Existing extraction is a supporting branch; mutation scoring and structural validation remain proposed.','#2576b6','#eaf3fc')
rect(65,1400,760,135,'#ffffff','#d6e8f9')
icon(86,1420,'database','#2576b6')
text(165,1440,'FireProtDB evidence extraction',23,'#172b46',700,645)
text(165,1474,'Map project proteins through UniProt accessions',18,'#42536b',400,645)
text(165,1504,'Retain matching mutation records and source measurements',18,'#42536b',400,645)
rect(900,1400,830,135,'#ffffff','#91aecb',dashed=True)
icon(921,1420,'molecule','#2576b6')
text(1000,1440,'Mutation exploration + structure review',23,'#172b46',700,705)
text(1000,1474,'Proposed: residue mapping, mutant assessment, structural context',18,'#42536b',400,705)
text(1000,1504,'Requires validated methods and experimental confirmation',18,'#42536b',400,705)
arrow([(825,1467),(900,1467)],'#2576b6',dashed=True)
text(65,1593,'SOLID = IMPLEMENTED     DASHED = PROPOSED     •     TPA / PET research scope',18,'#526179',600)
svg.append('</svg>')
(OUT/'enzaime-system-architecture.svg').write_text('\n'.join(svg),encoding='utf-8')
ET.indent(mx)
ET.ElementTree(mx).write(OUT/'enzaime-system-architecture.drawio',encoding='utf-8',xml_declaration=True)
print('Created SVG and editable draw.io diagram.')
