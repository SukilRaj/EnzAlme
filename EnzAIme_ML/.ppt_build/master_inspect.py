import zipfile,lxml.etree as E
z=zipfile.ZipFile(r'C:\Users\Welcome\Downloads\ProjectReview_EnzymeDE_Updated.pptx');ns={'a':'http://schemas.openxmlformats.org/drawingml/2006/main','p':'http://schemas.openxmlformats.org/presentationml/2006/main'}
for n in ['ppt/slideLayouts/slideLayout2.xml','ppt/slideMasters/slideMaster1.xml']:
 r=E.fromstring(z.read(n));print(n);print(E.tostring(r).decode()[:6500])
