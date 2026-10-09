from pathlib import Path
import json,hashlib
import pypdfium2 as pdfium
from PIL import Image,ImageDraw
R=Path(__file__).parent;rows=json.loads((R/'live_final.json').read_text(encoding='utf8'))['rows'];out=[];seen=set()
for row in rows:
 for d in row['evidence'].get('manuals',[]):
  if not d.get('verified') or d['sha256'] in seen:continue
  raw=(R/'captures'/d['file']).read_bytes();assert hashlib.sha256(raw).hexdigest()==d['sha256'];seen.add(d['sha256']);pdf=pdfium.PdfDocument(raw);image=pdf[0].render(scale=1).to_pil();file='manual_'+str(row['id'])+'_cover.png';image.save(R/file);out.append({'id':row['id'],'file':file,'pdf':d['file'],'url':d['url'],'title':d['title'],'type':d['type'],'pages':len(pdf),'width':image.width,'height':image.height});pdf.close()
(R/'document_render.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8')
sheet=Image.new('RGB',(1200,((len(out)+3)//4)*380),'#ddd');draw=ImageDraw.Draw(sheet)
for i,x in enumerate(out):
 im=Image.open(R/x['file']).convert('RGB');im.thumbnail((280,345));px=i%4*300;py=i//4*380;sheet.paste(im,(px,py));draw.text((px+5,py+350),'ID '+str(x['id'])+' RU User Guide',fill='black')
sheet.save(R/'manual_contact_sheet.png');print(len(out),'distinct actual verified RU PDF covers rendered')
