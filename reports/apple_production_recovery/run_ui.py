"""Click the running application's real form; its ordinary embedded worker fetches live sources."""
import sys,json,time,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from playwright.sync_api import sync_playwright
from product_tool import jobs,card_evidence,discovery_trace
root=Path(__file__).resolve().parents[2];out=Path(__file__).parent;db=root/'data/batches.sqlite3'
before=jobs.list_jobs(db,84)[0]['id']
with sync_playwright() as pw:
 browser=pw.chromium.launch(headless=True,channel='chrome')
 page=browser.new_page(viewport={'width':1440,'height':1000})
 page.goto('http://127.0.0.1:8765/products/84',wait_until='domcontentloaded',timeout=20000)
 page.screenshot(path=str(out/'ui_before.png'),full_page=True)
 with page.expect_response(lambda r:'/products/84/search' in r.url and r.request.method=='POST') as response:
  page.get_by_role('button',name='Поставить в очередь',exact=True).click()
 print('Actual UI POST:',response.value.status,flush=True)
 start=time.monotonic();job=None
 while time.monotonic()-start<180:
  current=jobs.list_jobs(db,84)[0]
  if current['id']!=before:
   job=current
   if job['status'] not in jobs.ACTIVE:break
  time.sleep(2)
 if job is None or job['status'] in jobs.ACTIVE:raise RuntimeError('Production UI run did not finish within observation window')
 page.reload(wait_until='domcontentloaded')
 page.locator('details').filter(has=page.locator('summary',has_text='Ход работы')).first.evaluate('(e)=>e.open=true')
 page.screenshot(path=str(out/'ui_after.png'),full_page=True)
 (out/'ui_after.html').write_text(page.content(),encoding='utf8')
 browser.close()
ev=card_evidence.load(db,84,'apple')
result=dict(evidence_mode='actual_live_production_worker_from_UI_POST; no fixture injection',url='http://localhost:8765/products/84',
 product=jobs.get_product(db,84),job=job,events=jobs.list_events(db,job['id']),trace=discovery_trace.for_job(db,job['id']),
 evidence=ev,readiness=__import__('product_tool.apple_pipeline',fromlist=['card_readiness']).card_readiness(db,84),
 sources=jobs.get_source_pages(db,84),facts=jobs.get_facts(db,84),resolved=jobs.get_resolved(db,84),photos=jobs.get_photo_candidates(db,84))
(out/'actual_production.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str),encoding='utf8')
print(json.dumps(dict(job=job,readiness=result['readiness'],sources=[{k:s.get(k) for k in ('source_key','url','match_level','error')} for s in result['sources']],photos=[{k:p.get(k) for k in ('asset_key','selected','verified_width','verified_height','verified_bytes','verified_format')} for p in result['photos']]),ensure_ascii=False),flush=True)
