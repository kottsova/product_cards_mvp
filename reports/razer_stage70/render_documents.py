from pathlib import Path
import json
import pypdfium2 as pdfium
R=Path(__file__).parent;rows=json.loads((R/'corrected_replay_release.json').read_text(encoding='utf8'))['rows'];out=[];seen=set()
for row in rows:
 for d in row['evidence'].get('manuals',[]):
  if not d.get('verified') or d['sha256'] in seen:continue
  seen.add(d['sha256']);pdf=pdfium.PdfDocument(R/'captures'/d['file']);image=pdf[0].render(scale=1).to_pil();file='manual_'+str(row['id'])+'_cover.png';image.save(R/file);out.append({'id':row['id'],'file':file,'pdf':d['file'],'url':d['url'],'title':d['title'],'pages':len(pdf),'width':image.width,'height':image.height});pdf.close()
(R/'document_render.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8');print(len(out),'distinct genuine RU PDF covers rendered')
