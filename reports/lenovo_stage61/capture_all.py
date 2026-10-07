from pathlib import Path
import json,time,os,hashlib
from urllib.parse import urlsplit,parse_qs
from playwright.sync_api import sync_playwright
from product_tool.census.attended_support import looks_like_challenge
root=Path('reports/lenovo_stage61');out=root/'psref_captures';out.mkdir(exist_ok=True)
os.environ['PLAYWRIGHT_BROWSERS_PATH']=str(Path('.venv/playwright-browsers').resolve())
data=json.loads(Path('reports/lenovo_stage60/dataset_frozen.json').read_text(encoding='utf-8-sig'))
models=[{'article':'21ML005BUS'}]+data['models']
with sync_playwright() as pw:
 context=pw.chromium.launch_persistent_context(str((root/'attended_profile').resolve()),headless=False,viewport={'width':1400,'height':900})
 page=context.pages[0] if context.pages else context.new_page()
 records=[];current={}
 def finished(req):
  host=urlsplit(req.url).hostname
  if host!='psref.lenovo.com' or '/api/' not in req.url or '/auth/' in req.url:return
  if not any(x in req.url for x in ('GetInfoByKey','SpecData','/Photo/','ShowDocumentations')):return
  try:
   r=req.response();body=r.body()
   if len(body)>2000000:return
   filename=hashlib.sha256(body).hexdigest()+'.json';(out/filename).write_bytes(body)
   records.append({'url':r.url,'status':r.status,'content_type':r.headers.get('content-type',''),'sha256':filename[:-5],'file':filename,'authorization_present':bool(req.headers.get('authorization'))})
  except Exception as e:records.append({'url':req.url,'error':type(e).__name__})
 page.on('requestfinished',finished)
 for row in models:
  article=row['article'];records=[]
  url=f'https://psref.lenovo.com/Detail/Model?M={article}'
  try:
   page.goto(url,wait_until='domcontentloaded',timeout=30000)
   for _ in range(30):
    page.wait_for_timeout(500)
    if any('/Photo/' in r['url'] for r in records):break
    if looks_like_challenge(page.url,page.content()):break
   page.wait_for_timeout(1000)
   html=page.content();text=page.locator('body').inner_text(timeout=5000)
   (out/f'{article}.html').write_text(html,encoding='utf-8')
   (out/f'{article}.txt').write_text(text,encoding='utf-8')
   manifest={'article':article,'entry_url':url,'final_url':page.url,'captured_at':time.time(),'flow':'attended passive frontend capture; no custom headers, stealth or challenge interaction','challenge':looks_like_challenge(page.url,html),'records':records,'dom_file':f'{article}.html'}
  except Exception as e:manifest={'article':article,'entry_url':url,'error':str(e),'records':records}
  (out/f'{article}.manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
  print(article,len(records),[(urlsplit(r['url']).path,r.get('status')) for r in records],flush=True)
 context.close()
