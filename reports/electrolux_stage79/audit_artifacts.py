"""Offline QA of actual downloaded bytes, never an additional live result."""
import json,hashlib,re
from pathlib import Path
from PIL import Image,ImageDraw,ImageOps
import pymupdf
R=Path(__file__).parent;Q=R/'qa';Q.mkdir(exist_ok=True);gallery=[];documents=[]
canvas=Image.new('RGB',(1600,2000),'#eeeeee');draw=ImageDraw.Draw(canvas)
for file in sorted((R/'release_live').glob('*/result.json'),key=lambda p:int(p.parent.name)):
 d=json.loads(file.read_text(encoding='utf8'));ev=d['evidence'];pid=d['input']['id']
 for m in ev.get('image_measurements',[]):
  if not m.get('accepted'):continue
  path=file.parent/'captures'/(m['sha256']+'.img');raw=path.read_bytes();assert hashlib.sha256(raw).hexdigest()==m['sha256']
  with Image.open(path) as im:
   assert im.size==(m['width'],m['height']);n=len(gallery);x=(n%4)*400;y=(n//4)*400;thumb=ImageOps.contain(im.convert('RGB'),(380,345));canvas.paste(thumb,(x+(400-thumb.width)//2,y+45+(345-thumb.height)//2));draw.text((x+10,y+8),f'{pid}: {d["input"]["model"]} {m["width"]}x{m["height"]}',fill='black');draw.text((x+10,y+24),m['selection'],fill='black')
  gallery.append({'id':pid,'model':d['input']['model'],'product_code':ev['identity'].get('product_code'),'selected':m['identity_confirmed'],**m,'file':str(path.relative_to(R))})
 for item in ev.get('document_inventory',[]):
  entry={'id':pid,**item}
  if item.get('verified'):
   path=file.parent/'captures'/item['file'];assert hashlib.sha256(path.read_bytes()).hexdigest()==item['sha256']
   with pymupdf.open(path) as pdf:
    text='\n'.join(p.get_text() for p in pdf);entry.update(pages=len(pdf),explicit_regulations=list(dict.fromkeys(re.findall(r'(?:EU|EC)\)?\s*\d{2,4}/\d{2,4}',text))))
    if pid in (1,2) and item['type']=='User Manual':
     output=Q/f'guide_{pid}_cover.png';pdf[0].get_pixmap(matrix=pymupdf.Matrix(1.1,1.1)).save(output);entry['cover_preview']=str(output.relative_to(R))
     matches=[(i,p.get_text()) for i,p in enumerate(pdf) if 'Control panel description' in p.get_text()]
     entry['control_panel_evidence']=[{'page':i+1,'text':t} for i,t in matches]
     if matches:pdf[matches[0][0]].get_pixmap(matrix=pymupdf.Matrix(1.2,1.2)).save(Q/f'guide_{pid}_controls.png')
  documents.append(entry)
canvas.save(Q/'gallery_contact_sheet.png')
(R/'gallery_audit.json').write_bytes(json.dumps({'origin':'offline QA of actual live downloads; identity candidates remain candidates','byte_verified':len(gallery),'selected':sum(x['selected'] for x in gallery),'images':gallery},ensure_ascii=False,indent=2).encode())
(R/'document_audit.json').write_bytes(json.dumps({'origin':'offline QA of actual live documents; PDF facts not merged into PDP specs','documents':documents},ensure_ascii=False,indent=2).encode())
print({'byte_verified':len(gallery),'selected':sum(x['selected'] for x in gallery),'documents_verified':sum(bool(x.get('verified')) for x in documents)},flush=True)
