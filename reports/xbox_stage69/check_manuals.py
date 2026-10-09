"""Independent visual/PDFium QA of actual fetched optional manuals."""
from pathlib import Path
import json,hashlib,re
import pypdfium2 as pdfium
R=Path(__file__).parent;out=[]
for p in (R/'live_final_e'/'xbox_captures').glob('*.bin'):
 if not p.read_bytes().startswith(b'%PDF-'):continue
 pdf=pdfium.PdfDocument(p);pages=[];text=''
 for i in range(len(pdf)):
  page=pdf[i];t=page.get_textpage().get_text_range();text+=t+'\n'
  legacy_ru=len(re.findall(r'[Ǐ-ɏ]',t))>100
  if i==0 or (not any(v.get('legacy_ru') or v['russian'] for v in pages) and (len(re.findall(r'[А-Яа-яЁё]',t))>100 or legacy_ru)):
   name=p.stem+f'_page_{i+1}.png';page.render(scale=1.3).to_pil().save(R/name)
   pages.append(dict(page=i+1,file=name,russian=len(re.findall(r'[А-Яа-яЁё]',t))>100,legacy_ru=legacy_ru,text_excerpt=t[:800]))
 out.append(dict(file=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),pages=len(pdf),russian_chars=len(re.findall(r'[А-Яа-яЁё]',text)),rendered=pages,text_excerpt=text[:1500]))
 pdf.close()
(R/'document_render.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(out,ensure_ascii=False,indent=2)[:6000])
