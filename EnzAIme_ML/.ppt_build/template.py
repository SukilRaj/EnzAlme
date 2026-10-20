import zipfile, posixpath, copy, json
from pathlib import Path
from lxml import etree as E
ns={'a':'http://schemas.openxmlformats.org/drawingml/2006/main','p':'http://schemas.openxmlformats.org/presentationml/2006/main','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
rel_ns='http://schemas.openxmlformats.org/package/2006/relationships'
ct_ns='http://schemas.openxmlformats.org/package/2006/content-types'
original=zipfile.ZipFile(r'C:\Users\Welcome\Downloads\ProjectReview_EnzymeDE_Updated.pptx')
draft=zipfile.ZipFile('.ppt_build/content.pptx')
files={n:draft.read(n) for n in draft.namelist()}
layout=E.fromstring(original.read('ppt/slideLayouts/slideLayout2.xml'))
bg=copy.deepcopy(layout.find('p:cSld/p:bg',ns))
lr=E.fromstring(original.read('ppt/slideLayouts/_rels/slideLayout2.xml.rels'))
rid=bg.find('.//a:blip',ns).get('{'+ns['r']+'}embed')
target=next(x.get('Target') for x in lr if x.get('Id')==rid)
source=posixpath.normpath('ppt/slideLayouts/'+target)
ext=Path(source).suffix
media='ppt/media/source_college_template'+ext
files[media]=original.read(source)
master_name='ppt/slideMasters/slideMaster1.xml'
master=E.fromstring(files[master_name]); cs=master.find('p:cSld',ns)
old=cs.find('p:bg',ns)
if old is not None:cs.remove(old)
bg.find('.//a:blip',ns).set('{'+ns['r']+'}embed','rIdSourceTemplate')
cs.insert(0,bg)
date=copy.deepcopy(layout.find('p:cSld/p:spTree/p:sp',ns))
date.find('p:nvSpPr/p:cNvPr',ns).set('id','900')
date.find('.//a:t',ns).text='October 1, 2026'
date.find('p:spPr/a:xfrm/a:off',ns).set('x','914400')
for pp in date.findall('.//a:p',ns):
 pr=pp.find('a:pPr',ns)
 if pr is None:pr=E.Element('{'+ns['a']+'}pPr');pp.insert(0,pr)
 pr.set('marL','0');pr.set('indent','0');E.SubElement(pr,'{'+ns['a']+'}buNone')
cs.find('p:spTree',ns).append(date)
files[master_name]=E.tostring(master,xml_declaration=True,encoding='UTF-8',standalone=True)
mr_name='ppt/slideMasters/_rels/slideMaster1.xml.rels'
mr=E.fromstring(files[mr_name]);E.SubElement(mr,'{'+rel_ns+'}Relationship',Id='rIdSourceTemplate',Type=ns['r']+'/image',Target='../media/'+Path(media).name)
files[mr_name]=E.tostring(mr,xml_declaration=True,encoding='UTF-8',standalone=True)
for name in list(files):
 if name.startswith('ppt/slides/slide') and name.endswith('.xml'):
  root=E.fromstring(files[name]); b=root.find('p:cSld/p:bg',ns)
  if b is not None:b.getparent().remove(b)
  for x in root.findall('p:timing',ns)+root.findall('p:transition',ns):root.remove(x)
  files[name]=E.tostring(root,xml_declaration=True,encoding='UTF-8',standalone=True)
ct=E.fromstring(files['[Content_Types].xml'])
if not any(x.get('Extension')==ext[1:] for x in ct):E.SubElement(ct,'{'+ct_ns+'}Default',Extension=ext[1:],ContentType='image/jpeg' if ext.lower() in ['.jpg','.jpeg'] else 'image/png')
files['[Content_Types].xml']=E.tostring(ct,xml_declaration=True,encoding='UTF-8',standalone=True)
with zipfile.ZipFile('.ppt_build/candidate.pptx','w',zipfile.ZIP_DEFLATED) as z:
 for name,content in files.items():z.writestr(name,content)
print('Original college background and date shape preserved; static candidate ready')

