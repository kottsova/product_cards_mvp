"""Common bounded image-byte verification of one selected official render per row."""
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from product_tool import jobs,photo_metadata
R=Path(__file__).parent;db=R/'live_release.sqlite3';out=[]
for pid in range(1,11):
 photos=[p for p in jobs.get_photo_candidates(db,pid) if p['selected'] and p['kind']=='product_gallery']
 if not photos:continue
 p=photos[0]
 try:
  info=photo_metadata.inspect_saved_photo(p['url'],'hyperx',R/'hyperx_fetch_log.json')
  jobs.save_photo_metadata(db,pid,p['id'],p['url'],width=info['width'],height=info['height'],size_bytes=info['size_bytes'],image_format=info['format'])
  out.append({'id':pid,'url':p['url'],'verified':True,**info})
 except Exception as e:out.append({'id':pid,'url':p['url'],'verified':False,'error':str(e)})
 (R/'photo_verification.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8')
 print(pid,out[-1]['verified'],flush=True)
