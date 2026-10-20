import zipfile,lxml.etree as E,csv,json; csv.field_size_limit(100000000)
z=zipfile.ZipFile(r'C:\Users\Welcome\Downloads\ProjectReview_EnzymeDE_Updated.pptx'); ns={'a':'http://schemas.openxmlformats.org/drawingml/2006/main','p':'http://schemas.openxmlformats.org/presentationml/2006/main'}
r=E.fromstring(z.read('ppt/slides/slide2.xml')); print(E.tostring(r.find('p:cSld',ns)[0])[:250]); print(z.read('ppt/slides/_rels/slide2.xml.rels').decode())
with open('master_dataset.csv',encoding='utf-8-sig',newline='') as f:
 rows=list(csv.DictReader(f)); print('MASTER',len(rows)); print('FIELDS',list(rows[0]));
 for k in rows[0]:
  if 'activity' in k or 'assay' in k:
   vals=[]
   for r in rows:
    try: v=json.loads(r[k]); vals.append(len(v) if isinstance(v,list) else 0)
    except: pass
   print(k,sum(vals))
