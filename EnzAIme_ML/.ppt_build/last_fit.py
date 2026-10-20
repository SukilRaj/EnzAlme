from pathlib import Path
import zipfile
p=Path('outputs/ProjectReview_EnzAIme_Final_Review.pptx');z=zipfile.ZipFile(p)
old='Verification includes embedding finiteness, protein split checks and a saved API compatibility probe. Software checks do not establish predictive validity.'
new='Checks cover embedding validity, protein splits and a saved API probe. These checks do not validate prediction quality.'
with zipfile.ZipFile('.ppt_build/candidate_final.pptx','w',zipfile.ZIP_DEFLATED) as out:
 for n in z.namelist():
  data=z.read(n)
  if n=='ppt/slides/slide37.xml':
   assert old.encode() in data
   data=data.replace(old.encode(),new.encode())
  out.writestr(n,data)
f=Path('.ppt_build/finalize_final.mjs');s=f.read_text(encoding='utf-8-sig').replace('/.ppt_build/candidate.pptx','/.ppt_build/candidate_final.pptx').replace('validation_final.json','validation_delivery.json');Path('.ppt_build/finalize_delivery.mjs').write_text(s,encoding='utf-8')
