from pathlib import Path
import json,os,hashlib
from playwright.sync_api import sync_playwright
from product_tool.census.attended_support import looks_like_challenge
r=Path('reports/jbl_stage62');o=r/'jbl_captures';o.mkdir(exist_ok=True);rows=json.loads((r/'dataset_frozen.json').read_text())['models'];rows=[{'article':'JBLFLIP6BLKEU'}]+rows
os.environ['PLAYWRIGHT_BROWSERS_PATH']=str(Path('.venv/playwright-browsers').resolve());results=[];stopped=set()
with sync_playwright() as pw:
 c=pw.chromium.launch_persistent_context(str((r/'attended_profile').resolve()),headless=False,viewport={'width':1440,'height':1000});p=c.pages[0]
 for row in rows:
  article=row['article'];records=[]
  for host in ['uk.jbl.com','de.jbl.com']:
   url='https://'+host+'/'+article+'.html'
   if host in stopped:records.append({'url':url,'region':host.split('.')[0],'reason':'host_stopped','status':403});continue
   try:
    z=p.goto(url,wait_until='domcontentloaded',timeout=25000);p.wait_for_timeout(1200);html=p.content();text=p.locator('body').inner_text(timeout=3000);challenge=looks_like_challenge(p.url,text)
    item={'article':article,'url':url,'final_url':p.url,'status':z.status if z else 0,'challenge':challenge,'provider':'attended_browser','region':host.split('.')[0]}
    if z and z.status==200 and not challenge:
     name=article+'_'+host.split('.')[0]+'.html';(o/name).write_text(html,encoding='utf-8');item.update(file=name,sha256=hashlib.sha256(html.encode()).hexdigest());records.append(item);break
    records.append(item)
    if z and z.status in {401,403,429} or challenge:stopped.add(host)
   except Exception as e:records.append({'url':url,'error':str(e)[:180]})
  (o/(article+'.manifest.json')).write_text(json.dumps({'article':article,'flow':'ordinary visible attended browser; no challenge interaction','records':records},indent=2),encoding='utf-8');results.append(records);print(article,[(i.get('status'),i.get('region')) for i in records],flush=True)
 c.close()
(r/'capture_results.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
