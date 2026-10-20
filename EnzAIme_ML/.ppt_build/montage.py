from PIL import Image,ImageOps,ImageDraw
from pathlib import Path
files=sorted(Path('.ppt_build/source_render').glob('*.PNG'),key=lambda p:int(''.join(filter(str.isdigit,p.stem))))
for start in range(0,len(files),20):
 canvas=Image.new('RGB',(1200,((min(20,len(files)-start)+3)//4)*244),'#cccccc')
 for j,p in enumerate(files[start:start+20]):
  im=Image.open(p); im.thumbnail((294,220)); x=j%4*300; y=j//4*244; canvas.paste(im,(x,y)); ImageDraw.Draw(canvas).text((x+6,y+222),p.stem,fill='black')
 canvas.save(f'.ppt_build/source_montage_{start}.jpg')
