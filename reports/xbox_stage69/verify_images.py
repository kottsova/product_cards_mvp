"""Independent full JPEG/PNG decode and inspection contact sheet."""
from pathlib import Path
import hashlib,json
from PIL import Image,ImageDraw
R=Path(__file__).parent;out=[];photos=json.loads((R/'photo_inspection.json').read_text(encoding='utf8'))
sheet=Image.new('RGB',(1000,300*((len(photos)+2)//3)),'white');draw=ImageDraw.Draw(sheet)
for i,m in enumerate(photos):
 p=R/m['file'];im=Image.open(p);im.verify();im=Image.open(p).convert('RGB');assert im.size==(m['width'],m['height']);assert hashlib.sha256(p.read_bytes()).hexdigest()==m['sha256'];im.thumbnail((300,250));x=(i%3)*333;y=(i//3)*300;sheet.paste(im,(x,y+25));draw.text((x+5,y+5),m['article'],fill='black');out.append(dict(file=str(p),full_decode=True,dimensions=im.size))
sheet.save(R/'photo_contact.png')
for p in R.glob('excel_*.png'):
 im=Image.open(p);im.verify();out.append(dict(file=str(p),full_decode=True))
(R/'image_validation.json').write_text(json.dumps(out,indent=2),encoding='utf8');print('Decoded',len(out),'images; contact sheet saved')
