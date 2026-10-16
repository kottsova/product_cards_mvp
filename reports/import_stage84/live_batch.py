"""Actual unchanged three-column upload -> UI batch -> default production worker."""
import json,sys,time,urllib.request
sys.stdout.reconfigure(encoding='utf8')
from pathlib import Path
from playwright.sync_api import sync_playwright
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from product_tool import jobs,storage,discovery_trace,readiness,attribute_projection,photo_inventory,card_evidence
root=Path(__file__).resolve().parents[2];out=Path(__file__).parent;phase=sys.argv[1] if len(sys.argv)>1 else 'live_initial'
dest=out/phase;dest.mkdir(exist_ok=True);db=root/'data/batches.sqlite3';batch=json.loads((out/'batch.json').read_text(encoding='utf8'))
ids=[p['id'] for p in batch['products'] if p['row_number'] in {2,3,4,5,6}]
observe='--observe' in sys.argv
previous={pid:None if observe else (jobs.list_jobs(db,pid) or [{'id':None}])[0]['id'] for pid in ids}
runtime=json.load(urllib.request.urlopen('http://127.0.0.1:8765/diagnostics/runtime'))
with sync_playwright() as pw:
 if not observe:
  browser=pw.chromium.launch(headless=True);page=browser.new_page(viewport={'width':1900,'height':1100})
  page.goto('http://127.0.0.1:8765/batches/'+batch['id'],wait_until='domcontentloaded')
  form=page.locator('#product-batch-form')
  for box in form.locator('[name="product_ids"]').all():box.uncheck()
  for pid in ids:form.locator(f'[name="product_ids"][value="{pid}"]').check()
  with page.expect_response(lambda r:'/batches/'+batch['id']+'/search' in r.url and r.request.method=='POST') as response:form.get_by_role('button',name='Поставить выбранные товары в очередь',exact=True).click()
  assert response.value.status==303
  browser.close()
pending=set(ids);start=time.monotonic();summary=[]
while pending and time.monotonic()-start<1500:
 for pid in list(pending):
  job=(jobs.list_jobs(db,pid) or [{}])[0]
  if job.get('id')==previous[pid] or job.get('status') in jobs.ACTIVE:continue
  product=jobs.get_product(db,pid);kind=photo_inventory.evidence_kind(product)
  result=dict(observation='actual_UI_default_factories_no_provider_injection',runtime=runtime,product=product,job=job,trace=discovery_trace.for_job(db,job['id']),events=jobs.list_events(db,job['id']),sources=jobs.get_source_pages(db,pid),facts=jobs.get_facts(db,pid),canonical=attribute_projection.final_attribute_rows(db,pid),photos=photo_inventory.enriched_photos(db,pid),evidence=card_evidence.load(db,pid,kind),readiness=readiness.card_readiness(db,pid))
  (dest/f'{pid}.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
  row=dict(id=pid,brand=product['brand'],name=product['name'],model=product.get('model'),supplier_article=product.get('supplier_article'),discovery_name=product.get('discovery_name'),status=job['status'],started_at=job['started_at'],finished_at=job['finished_at'],specs=len(result['canonical']),photos=sum(p['identity_confirmed'] for p in result['photos']),readiness=result['readiness']['verdict'],sources=[s['url'] for s in result['sources'] if s['url'] and not s['error']])
  summary.append(row);(dest/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(row,ensure_ascii=False),flush=True);pending.remove(pid)
 if pending:time.sleep(2)
assert not pending,pending
