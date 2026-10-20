from pathlib import Path
import zipfile, xml.etree.ElementTree as E, re, json, posixpath
source=Path(r'C:\Users\Welcome\Downloads\PET_Degradation_Overview.pptx')
out=Path('docs/presentation_study_guide_2026-10-12')
(out/'source_images').mkdir(parents=True,exist_ok=True)
ns={'a':'http://schemas.openxmlformats.org/drawingml/2006/main','p':'http://schemas.openxmlformats.org/presentationml/2006/main','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
with zipfile.ZipFile(source) as z:
    rels={e.attrib['Id']:e.attrib['Target'] for e in E.fromstring(z.read('ppt/_rels/presentation.xml.rels'))}
    order=[posixpath.normpath(posixpath.join('ppt',rels[e.attrib['{'+ns['r']+'}id']])) for e in E.fromstring(z.read('ppt/presentation.xml')).findall('p:sldIdLst/p:sldId',ns)]
    slides=[]
    for i,part in enumerate(order,1):
        root=E.fromstring(z.read(part))
        paras=[''.join(t.text or '' for t in p.iter() if t.tag.endswith('}t')) for p in root.findall('.//a:p',ns)]
        relpart=posixpath.join(posixpath.dirname(part),'_rels',posixpath.basename(part)+'.rels')
        rs={e.attrib['Id']:e.attrib['Target'] for e in E.fromstring(z.read(relpart))} if relpart in z.namelist() else {}
        images=[]
        for j,b in enumerate(root.findall('.//a:blip',ns)):
            rid=b.attrib.get('{'+ns['r']+'}embed')
            if rid not in rs:continue
            path=posixpath.normpath(posixpath.join(posixpath.dirname(part),rs[rid]))
            dst=out/'source_images'/f'slide-{i:02d}-{j+1}{Path(path).suffix}'
            dst.write_bytes(z.read(path)); images.append(str(dst))
        slides.append({'slide':i,'part':part,'paragraphs':paras,'images':images})
    (out/'slide_inventory.json').write_text(json.dumps(slides,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Deck order:',[(s['slide'],s['part']) for s in slides if s['slide']>=67])
    for s in slides:
        if s['slide'] in [21,25,27,70,71,72,73]:print(s['slide'],s['images'])
