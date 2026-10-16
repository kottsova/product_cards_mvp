"""Five-brand actual UI retry on the final source, no provider injection."""
import json,sys,time,urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[2];sys.path.insert(0,str(root));out=Path(__file__).parent
from product_tool import jobs,storage,discovery_trace
initial=json.loads((out/'mixed/acceptance.json').read_text(encoding='utf8'));batch=initial['batch_id'];ids=initial['ids'][:5];db=root/'data/batches.sqlite3';base='http://127.0.0.1:8765'
previous={pid:jobs.list_jobs(db,pid)[0]['id'] for pid in ids};proof=dict(ids=ids,batch_id=batch,runtime=json.load(urllib.request.urlopen(base+'/diagnostics/runtime')),polls=[])
with sync_playwright() as pw:
 browser=pw.chromium.launch(headless=True);page=browser.new_page(viewport={'width':1900,'height':1080})
 for attempt in range(2):
  try:page.goto(base+'/batches/'+batch,wait_until='domcontentloaded',timeout=15000);break
  except Exception:
   if attempt:raise
 page.locator('#select-none').click()
 for pid in ids:page.locator(f'[name="product_ids"][value="{pid}"]').check()
 page.get_by_role('button',name='Повторить выбранные',exact=True).click();page.wait_for_load_state('domcontentloaded')
 # A second immediate click is explicitly tested: active jobs must not multiply.
 page.get_by_role('button',name='Повторить выбранные',exact=True).click();page.wait_for_load_state('domcontentloaded')
 token='final-source-stability';page.evaluate('(value)=>window.stage85Document=value',token)
 def collect(response):
  if response.url==base+f'/batches/{batch}/progress' and response.status==200:proof['polls'].append(dict(at=time.time(),state=response.json()))
 page.on('response',collect);start=time.monotonic()
 while time.monotonic()-start<1500:
  page.wait_for_timeout(1000);assert page.evaluate('window.stage85Document')==token
  if proof['polls']:
   rows={r['id']:r for r in proof['polls'][-1]['state']['rows']}
   if all(rows[pid]['job_id']!=previous[pid] and rows[pid]['final_status'] for pid in ids):break
 proof['results']=[]
 for pid in ids:
  job=jobs.list_jobs(db,pid)[0];assert job['id']!=previous[pid] and job['status'] not in jobs.ACTIVE
  assert len(jobs.list_jobs(db,pid))==2,'duplicate queued retry'
  with storage._connection(db) as c:phases=[dict(x) for x in c.execute('SELECT phase,created_at FROM job_phase_events WHERE job_id=? ORDER BY id',(job['id'],))]
  proof['results'].append(dict(product=jobs.get_product(db,pid),job=job,phases=phases,sources=jobs.get_source_pages(db,pid),trace=discovery_trace.for_job(db,job['id'])))
 proof['no_full_reload']=True;proof['no_duplicate_jobs']=True;proof['seconds']=time.monotonic()-start
 page.screenshot(path=str(out/'stability_final.png'),full_page=True)
 (out/'stability.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf8');print('Final source stability complete',flush=True);browser.close()
