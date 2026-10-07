from pathlib import Path
import json,os,hashlib
from urllib.parse import urlsplit,urljoin
from playwright.sync_api import sync_playwright
root=Path('reports/lenovo_stage61');out=root/'additional';out.mkdir(exist_ok=True)
os.environ['PLAYWRIGHT_BROWSERS_PATH']=str(Path('.venv/playwright-browsers').resolve())
urls=['https://download.lenovo.com/manual/x1_carbon_g12/index.html','https://download.lenovo.com/pccbbs/pubs/thinkbook_14_16_g6/index.html','https://pcsupport.lenovo.com/us/en/products/laptops-and-netbooks/thinkpad-t-series-laptops/thinkpad-t14-gen-5-type-21ml-21mm/21ml/21ml005bus']
records=[];results=[]
with sync_playwright() as pw:
 context=pw.chromium.launch_persistent_context(str((root/'attended_profile').resolve()),headless=False,accept_downloads=True)
 page=context.pages[0]
 def finished(req):
  if '/api/' not in req.url or 'lenovo.com' not in (urlsplit(req.url).hostname or '') or '/auth/' in req.url:return
  try:
   r=req.response();b=r.body()
   if len(b)>4000000:return
   name=hashlib.sha256(b).hexdigest()+'.response';(out/name).write_bytes(b);records.append({'url':req.url,'status':r.status,'file':name})
  except Exception:pass
 page.on('requestfinished',finished)
 for n,url in enumerate(urls):
  records=[]
  try:
   r=page.goto(url,wait_until='domcontentloaded',timeout=30000);page.wait_for_timeout(5000);(out/f'page{n}.html').write_text(page.content(),encoding='utf-8');(out/f'page{n}.txt').write_text(page.locator('body').inner_text(),encoding='utf-8');links=page.locator('a[href]').evaluate_all('(xs)=>xs.map(x=>({url:x.href,text:x.innerText}))');results.append({'url':url,'status':r.status,'links':links,'records':records});print(url,r.status,len(links),flush=True)
  except Exception as e:results.append({'url':url,'error':str(e)})
 (root/'additional_probe.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
 page.goto('https://psref.lenovo.com/Detail/Model?M=21KC0029MH',wait_until='domcontentloaded',timeout=30000);page.wait_for_timeout(3000)
 try:
  with page.expect_download(timeout=20000) as dl:page.locator('.btnExport').filter(has_text='Excel').first.click()
  download=dl.value;download.save_as(str(out/'psref_exact_export.xlsx'));print('PSREF Excel downloaded',flush=True)
 except Exception as e:print('PSREF Excel',type(e).__name__,flush=True)
 context.close()
