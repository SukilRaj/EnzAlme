import zipfile, lxml.etree as E, json
from pathlib import Path
p=Path(r'C:\Users\Welcome\Downloads\ProjectReview_EnzymeDE_Updated.pptx')
z=zipfile.ZipFile(p); ns={'a':'http://schemas.openxmlformats.org/drawingml/2006/main','p':'http://schemas.openxmlformats.org/presentationml/2006/main'}
slides=[]
for name in sorted([x for x in z.namelist() if __import__('re').match(r'ppt/slides/slide\d+\.xml$',x)],key=lambda x:int(__import__('re').search(r'slide(\d+)',x)[1])):
 r=E.fromstring(z.read(name)); texts=r.xpath('//a:t/text()',namespaces=ns); slides.append({'part':name,'text':texts})
print(json.dumps(slides,ensure_ascii=False,indent=1))
Path('.ppt_build/source_text.json').write_text(json.dumps(slides,ensure_ascii=False,indent=2),encoding='utf-8')
r=E.fromstring(z.read('ppt/presentation.xml')); print('SIZE',r.find('p:sldSz',ns).attrib)
print('FONTS', sorted(set(t for s in z.namelist() if s.endswith('.xml') and ('slides/' in s or 'theme/' in s) for t in E.fromstring(z.read(s)).xpath('//a:latin/@typeface',namespaces=ns))))
