"""Read-only render of the newly discovered US CFI-2015 manual pages."""
from pathlib import Path
import json,hashlib
import pypdfium2 as pdfium
r=Path('reports/playstation_stage67');a=json.loads((r/'replay_acceptance.json').read_text(encoding='utf-8'));out=[]
for m in a['results'][8]['evidence']['manuals']:
 p=r/'playstation_captures'/(hashlib.sha256(m['url'].encode()).hexdigest()[:20]+'.pdf');assert hashlib.sha256(p.read_bytes()).hexdigest()==m['sha256']
 pdf=pdfium.PdfDocument(p)
 for i in range(len(pdf)):
  page=pdf[i];text=page.get_textpage().get_text_range()
  if m['type']=='Quick Start' or ('Specifications' in text and 'Main Processor' in text):
   name='CFI-2015A_'+m['type'].replace(' ','_')+f'_page_{i+1}.png';page.render(scale=1.4).to_pil().save(r/name);out.append(dict(type=m['type'],page=i+1,file=name,source_url=m['url'],sha256=m['sha256']));break
(r/'document_render.json').write_text(json.dumps(out,indent=2),encoding='utf-8');print(out)
