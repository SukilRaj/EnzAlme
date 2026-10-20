from pathlib import Path
import json,re,hashlib
from html.parser import HTMLParser
out=Path('docs/presentation_study_guide_2026-10-12')
md=(out/'EnzAIme_Slide_by_Slide_Guide.md').read_text(encoding='utf-8')
slides=[int(x) for x in re.findall(r'^## Slide (\d+) ',md,re.M)]
assert slides==list(range(1,84)),slides
class Inspect(HTMLParser):
    def __init__(self):super().__init__();self.ids=[];self.images=[];self.links=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if 'id' in a:self.ids.append(a['id'])
        if tag=='img':self.images.append(a['src'])
        if tag=='a' and a.get('href','').startswith('#'):self.links.append(a['href'][1:])
p=Inspect();p.feed((out/'index.html').read_text(encoding='utf-8'))
assert len(p.ids)==len(set(p.ids))
assert all(x in p.ids for x in p.links)
assert all((out/x).is_file() for x in p.images)
manifest=json.loads((out/'source_manifest.json').read_text())
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in manifest['sources'].items())
print(json.dumps({'slide_sections':len(slides),'formula_displays':len(re.findall(r'\$\$',md))//2,'linked_images':len(p.images),'navigation_targets':len(p.links),'source_hashes_match':True,'browser_preview':'Not performed: local file protocol is blocked by browser policy.'}))
