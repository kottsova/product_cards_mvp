from pathlib import Path
import json,os,hashlib
from playwright.sync_api import sync_playwright
from product_tool.census.attended_support import looks_like_challenge
r=Path('reports/jbl_stage62');o=r/'attended';o.mkdir(exist_ok=True)
os.environ['PLAYWRIGHT_BROWSERS_PATH']=str(Path('.venv/playwright-browsers').resolve());logs=[]
with sync_playwright() as pw:
 c=pw.chromium.launch_persistent_context(str((r/'attended_profile').resolve()),headless=False,viewport={'width':1440,'height':1000})
 p=c.pages[0]
 for name,url in [('baseline','https://de.jbl.com/JBLFLIP6BLKEU.html'),('global','https://global.jbl.com/bluetooth-speakers/JBLFLIP6RED.html'),('us','https://www.jbl.com/bluetooth-speakers/FLIP-6-.html'),('support','https://support.jbl.com/gb/en/speakers/speakers-portable/FLIP-6-.html')]:
  try:
   z=p.goto(url,wait_until='domcontentloaded',timeout=30000);p.wait_for_timeout(2500);html=p.content();text=p.locator('body').inner_text(timeout=4000);(o/(name+'.html')).write_text(html,encoding='utf-8');(o/(name+'.txt')).write_text(text,encoding='utf-8');challenge=looks_like_challenge(p.url,text);logs.append({'url':url,'final_url':p.url,'status':z.status if z else None,'challenge':challenge,'file':name+'.html','sha256':hashlib.sha256(html.encode()).hexdigest(),'text_length':len(text)});print(logs[-1],flush=True)
  except Exception as e:logs.append({'url':url,'error':str(e)[:200]});print(logs[-1],flush=True)
 c.close()
(r/'attended_probe.json').write_text(json.dumps(logs,indent=2),encoding='utf-8')
