from pathlib import Path
import json,time,re,os
from playwright.sync_api import sync_playwright
root=Path('reports/lenovo_stage61');root.mkdir(exist_ok=True)
os.environ['PLAYWRIGHT_BROWSERS_PATH']=str(Path('.venv/playwright-browsers').resolve())
log=[]
with sync_playwright() as pw:
 context=pw.chromium.launch_persistent_context(str((root/'attended_profile').resolve()),headless=False,viewport={'width':1440,'height':1100})
 page=context.pages[0] if context.pages else context.new_page()
 def response(r):
  if 'psref.lenovo.com' not in r.url:return
  event={'url':r.url,'status':r.status,'method':r.request.method,'content_type':r.headers.get('content-type',''),'authorization_present':bool(r.request.headers.get('authorization')),'cookie_present':bool(r.request.headers.get('cookie'))}
  if '/api/' in r.url and '/auth/' not in r.url:
   try:
    body=r.body();filename=f'api_{len(log):03}.response';(root/filename).write_bytes(body);event['payload_file']=filename;event['bytes']=len(body)
   except Exception as e:event['read_error']=str(e)[:150]
  log.append(event)
 page.on('response',response)
 for name,url in [('baseline','https://psref.lenovo.com/Detail/ThinkPad/ThinkPad_T14_Gen_5_Intel?M=21ML005BUS'),('monitor','https://psref.lenovo.com/Detail/ThinkVision_P40w_20?M=62C1GAT6EU')]:
  try:
   page.goto(url,wait_until='domcontentloaded',timeout=45000);page.wait_for_timeout(20000)
   text=page.locator('body').inner_text(timeout=5000);(root/f'browser_{name}.txt').write_text(text,encoding='utf-8');(root/f'browser_{name}.html').write_text(page.content(),encoding='utf-8');page.screenshot(path=str(root/f'browser_{name}.png'),full_page=True)
   print(name,len(text),text[:180],flush=True)
  except Exception as e:log.append({'page':url,'error':str(e)[:300]});print(name,str(e)[:180],flush=True)
 (root/'attended_api_probe.json').write_text(json.dumps({'flow':'visible ordinary Playwright persistent context; no protection bypass flags; frontend requests observed only','profile':'workspace separate attended session','events':log},indent=2),encoding='utf-8')
 context.close()
