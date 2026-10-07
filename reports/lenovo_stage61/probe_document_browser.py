from pathlib import Path
import json,os,time,hashlib
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright
root=Path('reports/lenovo_stage61');out=root/'manual_browser';out.mkdir(exist_ok=True)
os.environ['PLAYWRIGHT_BROWSERS_PATH']=str(Path('.venv/playwright-browsers').resolve())
rows=[r for r in json.loads((root/'manual_probe.json').read_text(encoding='utf-8')) if '.pdf' not in r['url']]
with sync_playwright() as pw:
 context=pw.chromium.launch_persistent_context(str((root/'attended_profile').resolve()),headless=False,viewport={'width':1400,'height':900})
 page=context.pages[0];events=[];results=[]
 def finished(req):
  if (urlsplit(req.url).hostname not in {'support.lenovo.com','pcsupport.lenovo.com'}) or ('/api/' not in req.url):return
  try:
   r=req.response();body=r.body()
   if len(body)>4000000:return
   filename=hashlib.sha256(body).hexdigest()+'.response';(out/filename).write_bytes(body)
   events.append({'url':req.url,'status':r.status,'file':filename})
  except Exception as e:events.append({'url':req.url,'error':type(e).__name__})
 page.on('requestfinished',finished)
 for row in rows:
  events=[]
  try:
   page.goto(row['url'],wait_until='domcontentloaded',timeout=30000);page.wait_for_timeout(6000)
   (out/row['file']).write_text(page.content(),encoding='utf-8');(out/(row['file']+'.txt')).write_text(page.locator('body').inner_text(),encoding='utf-8')
   links=page.locator('a[href]').evaluate_all('(xs)=>xs.map(x=>({url:x.href,text:x.innerText}))')
   item={**row,'events':events,'browser_links':links,'final_url':page.url};print(row['articles'],len(links),len(events),flush=True)
  except Exception as e:item={**row,'events':events,'error':str(e)}
  results.append(item);(root/'manual_browser_probe.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
 # Replay only the frontend-observed baseline endpoint with its own normal anonymous auth module.
 page.goto('https://psref.lenovo.com',wait_until='domcontentloaded',timeout=30000);page.wait_for_timeout(2000)
 result=page.evaluate("async()=>{const auth=await import('/assets/auth-CmCWbT8o.js');const h=await auth.g();const url='/api/model/Info/GetInfoByKey?ModelCode=21ML005BUS';const r=await fetch(url,{headers:h});return {url:new URL(url,location.origin).href,status:r.status,body:await r.text(),authorization_present:!!h.Authorization}}")
 (root/'baseline_psref_frontend_info.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print('baseline_psref',result['status'],result['body'],flush=True)
 context.close()
