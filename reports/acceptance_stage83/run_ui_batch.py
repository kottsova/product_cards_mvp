"""Actual browser form -> current listening app -> default embedded worker, no injection."""
import json,sys,time,urllib.request
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from playwright.sync_api import sync_playwright
from product_tool import jobs,readiness,discovery_trace,card_evidence,attribute_projection,photo_inventory
root=Path(__file__).resolve().parents[2];out=Path(__file__).parent;db=root/'data/batches.sqlite3'
phase,batch_id=sys.argv[1:3];ids=[int(x) for x in sys.argv[3:]];dest=out/phase;dest.mkdir(exist_ok=True)
previous={pid:(jobs.list_jobs(db,pid) or [{'id':None}])[0]['id'] for pid in ids}
runtime=json.load(urllib.request.urlopen('http://127.0.0.1:8765/diagnostics/runtime'))
(dest/'runtime.json').write_text(json.dumps(runtime,ensure_ascii=False,indent=2),encoding='utf8')
with sync_playwright() as pw:
 browser=pw.chromium.launch(headless=True,channel='chrome');page=browser.new_page(viewport={'width':1440,'height':1000})
 page.goto(f'http://127.0.0.1:8765/batches/{batch_id}',wait_until='domcontentloaded',timeout=30000)
 form=page.locator('#product-batch-form')
 for box in form.locator('input[name="product_ids"]').all():box.uncheck()
 for pid in ids:form.locator(f'input[name="product_ids"][value="{pid}"]').check()
 with page.expect_response(lambda r:f'/batches/{batch_id}/search' in r.url and r.request.method=='POST') as response:
  form.get_by_role('button',name='Поставить выбранные товары в очередь',exact=True).click()
 print('UI batch POST',response.value.status,'products',ids,flush=True)
 browser.close()
pending=set(ids);started=time.monotonic();summary=[]
while pending and time.monotonic()-started<1800:
 for pid in list(pending):
  latest=(jobs.list_jobs(db,pid) or [{}])[0]
  if latest.get('id')==previous[pid] or latest.get('status') in jobs.ACTIVE:continue
  p=jobs.get_product(db,pid);kind=photo_inventory.evidence_kind(p)
  result=dict(observation='actual_UI_batch_default_worker_no_factory_injection',runtime=runtime,
      product=p,job=latest,events=jobs.list_events(db,latest['id']),trace=discovery_trace.for_job(db,latest['id']),
      sources=jobs.get_source_pages(db,pid),facts=jobs.get_facts(db,pid),resolved=jobs.get_resolved(db,pid),
      canonical=attribute_projection.final_attribute_rows(db,pid),photos=photo_inventory.enriched_photos(db,pid),
      documents=jobs.get_documents(db,pid),evidence=card_evidence.load(db,pid,kind),
      semantics=card_evidence.load(db,pid,'semantic_decomposition'),readiness=readiness.card_readiness(db,pid))
  (dest/f'{pid}.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str),encoding='utf8')
  item=dict(id=pid,brand=p['brand'],article=p['search_code'],job=latest['status'],start=latest['started_at'],end=latest['finished_at'],specs=len(result['canonical']),photos=sum(x['identity_confirmed'] for x in result['photos']),readiness=result['readiness']['verdict'],sources=[s['url'] for s in result['sources'] if s['url'] and not s['error']])
  summary.append(item);(dest/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(item,ensure_ascii=False),flush=True);pending.remove(pid)
 if pending:time.sleep(2)
if pending:raise RuntimeError(f'Actual UI jobs still pending: {pending}; not reported as success')
