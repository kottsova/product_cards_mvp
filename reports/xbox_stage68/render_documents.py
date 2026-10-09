"""Read-only PDF QA using bundled PDFium; legacy text failure is reported."""
from pathlib import Path
import json,hashlib,re
import pypdfium2 as pdfium
R=Path(__file__).parent;out=[]
for p in (R/'observed').glob('*.pdf'):
 pdf=pdfium.PdfDocument(p);picked=[]
 for i in range(len(pdf)):
  page=pdf[i];text=page.get_textpage().get_text_range()
  if i==0 or (not any(x['russian'] for x in picked) and len(re.findall(r'[А-Яа-яЁё]',text))>100):
   name=p.stem+f'_page_{i+1}.png';page.render(scale=1.3).to_pil().save(R/name);picked.append(dict(page=i+1,file=name,russian=len(re.findall(r'[А-Яа-яЁё]',text))>100,text_excerpt=text[:500]))
  if len(picked)>=2:break
 out.append(dict(file=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),pages=len(pdf),rendered=picked))
(R/'document_render.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8');print(out,flush=True)
