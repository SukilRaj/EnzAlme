import zipfile,lxml.etree as E,json,posixpath
from pathlib import Path
z=zipfile.ZipFile(r'C:\Users\Welcome\Downloads\ProjectReview_EnzymeDE_Updated.pptx'); ns={'a':'http://schemas.openxmlformats.org/drawingml/2006/main','p':'http://schemas.openxmlformats.org/presentationml/2006/main'}
for i in [42,43,44,47,48]:
 r=E.fromstring(z.read(f'ppt/slides/slide{i}.xml')); rel=E.fromstring(z.read(f'ppt/slides/_rels/slide{i}.xml.rels')); rm={x.get('Id'):x.get('Target') for x in rel}
 for j,b in enumerate(r.findall('.//a:blip',ns)):
  target=rm[b.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed')]; part=posixpath.normpath('ppt/slides/'+target); out=Path(f'.ppt_build/screenshot_{i}_{j}'+Path(part).suffix); out.write_bytes(z.read(part)); print(out)
