"""Inspect actual downloaded gallery/documents; separate offline QA from live outcome."""
import json,hashlib,re,sys
from pathlib import Path
from PIL import Image,ImageDraw,ImageOps
import pymupdf
R=Path(__file__).parent;L=R/'qualified_live';Q=R/'qa';Q.mkdir(exist_ok=True)
gallery=[];documents=[];canvas=Image.new('RGB',(1600,1600),'#eeeeee');draw=ImageDraw.Draw(canvas)
for file in sorted(L.glob('*/result.json'),key=lambda p:int(p.parent.name)):
 d=json.loads(file.read_text(encoding='utf8'));ev=d['evidence'];pid=d['input']['id']
 for m in ev.get('image_measurements',[]):
  if not m.get('accepted'):continue
  path=file.parent/'captures'/(m['sha256']+'.img');raw=path.read_bytes();assert hashlib.sha256(raw).hexdigest()==m['sha256']
  with Image.open(path) as im:
   assert im.size==(m['width'],m['height']);n=len(gallery);x=(n%4)*400;y=(n//4)*400;thumb=ImageOps.contain(im.convert('RGB'),(380,355));canvas.paste(thumb,(x+(400-thumb.width)//2,y+35+(355-thumb.height)//2));draw.text((x+12,y+10),f'{pid}: {d["input"]["model"]} / {m["width"]}x{m["height"]}',fill='black')
  gallery.append({'id':pid,'model':d['input']['model'],'product_code':ev['identity'].get('product_code'),'selected':True,**m,'file':str(path.relative_to(R))})
 for item in ev.get('document_inventory',[]):
  entry={'id':pid,**item}
  if item.get('verified'):
   path=file.parent/'captures'/item['file'];raw=path.read_bytes();assert hashlib.sha256(raw).hexdigest()==item['sha256']
   with pymupdf.open(path) as pdf:
    text='\n'.join(p.get_text() for p in pdf);entry['pages']=len(pdf);entry['explicit_regulations']=list(dict.fromkeys(re.findall(r'(?:EU|EC)\)?\s*\d{2,4}/\d{2,4}',text)))
    entry['energy_context']={'annual_160_cycles':bool(re.search('160 drying cycles',text,re.I)),'eco_40_60':bool(re.search('eco 40-60',text,re.I)),'eco_program':bool(re.search('eco programme',text,re.I)),'conventional_fan_cycles':bool(re.search('fan.forced|conventional mode',text,re.I))}
    if item['type'] in {'User Manual','Energy Label','Product Fiche'}:
     output=Q/f'pdf_{pid}_{item["type"].replace(" ","_")}.png';pdf[0].get_pixmap(matrix=pymupdf.Matrix(1.1,1.1)).save(output);entry['cover_preview']=str(output.relative_to(R))
  documents.append(entry)
canvas.save(Q/'gallery_contact_sheet.png')
(R/'gallery_audit.json').write_bytes(json.dumps({'origin':'offline visual/byte QA of actual qualified_live downloads, not a new live success','selected_count':len(gallery),'unique_bytes':len({x['sha256'] for x in gallery}),'images':gallery},ensure_ascii=False,indent=2).encode('utf8'))
(R/'document_audit.json').write_bytes(json.dumps({'origin':'offline QA of actually live-discovered/downloaded PDFs; no PDF facts merged into PDP specs','documents':documents},ensure_ascii=False,indent=2).encode('utf8'))
print({'images':len(gallery),'documents':len(documents),'verified_documents':sum(bool(x.get('verified')) for x in documents)},flush=True)
