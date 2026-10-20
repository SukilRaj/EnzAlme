from pathlib import Path
import zipfile,json,hashlib
from lxml import etree as E
p=Path('outputs/ProjectReview_EnzAIme_Final_Review.pptx');z=zipfile.ZipFile(p); ns={'a':'http://schemas.openxmlformats.org/drawingml/2006/main','p':'http://schemas.openxmlformats.org/presentationml/2006/main'}
slides=[n for n in z.namelist() if __import__('re').fullmatch(r'ppt/slides/slide\d+\.xml',n)]
assert len(slides)==45
assert all(not E.fromstring(z.read(n)).findall('p:timing',ns) and not E.fromstring(z.read(n)).findall('p:transition',ns) for n in slides)
assert len([n for n in z.namelist() if n.startswith('ppt/notesSlides/notesSlide') and n.endswith('.xml')])==45
alltext=' '.join(t for n in slides for t in E.fromstring(z.read(n)).xpath('//a:t/text()',namespaces=ns))
for number in ['1423.11','3200.77','1918.29','3943.42','1592.12','3452.48','-86.87','-23.22','0.313','-0.227','0.239']:assert number in alltext,number
print('45 slides, static timing, 45 source notes, exact displayed ablation values verified')
