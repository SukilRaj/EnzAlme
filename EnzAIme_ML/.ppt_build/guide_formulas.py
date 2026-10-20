from pathlib import Path
import re
s=Path('docs/presentation_study_guide_2026-10-12/EnzAIme_Slide_by_Slide_Guide.md').read_text(encoding='utf-8')
for i,f in enumerate(re.findall(r'\$\$(.*?)\$\$',s,re.S),1): print(i,repr(f))
