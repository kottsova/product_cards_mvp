"""Frozen rows through worker; phases distinguish actual live and offline."""
import sys,json,hashlib,time,sqlite3
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from product_tool import jobs,worker,readiness,card_evidence,attribute_projection,discovery_trace
from product_tool.fetch_history import latest_source_snapshot
R=Path(__file__).parent
phase=sys.argv[1]
raw=(R/'frozen_inputs.json').read_bytes()
assert hashlib.sha256(raw).hexdigest()==(R/'frozen_inputs.sha256').read_text().strip()
db=R/(phase+'.sqlite3');assert not db.exists()
jobs.initialize(db)
rows=json.loads(raw)['rows']
with sqlite3.connect(db) as c:
 c.execute("INSERT INTO batches VALUES ('hx72','HyperX Stage 72.xlsx','Products','{}','2026-10-10')")
 for p in rows:c.execute("INSERT INTO products (batch_id,row_number,name,brand,search_code,alternate_code,category,needs_confirmation,issues_json,original_values_json) VALUES ('hx72',?,?, 'HyperX',?, '',?,0,'[]',?)",(p['id'],p['name'],p['article'],p['category'],json.dumps(p)))
out={'phase':phase,'origin':'actual live HTTP worker; no replay','input_sha256':hashlib.sha256(raw).hexdigest(),'rows':[]}
for p in rows:
 jid=jobs.enqueue(db,p['id'],[1,2,3,4,6]);start=time.monotonic()
 worker.run_once(db)
 item={'id':p['id'],'input':p,'elapsed':time.monotonic()-start,'job':jobs.list_jobs(db,p['id'])[0],'sources':jobs.get_source_pages(db,p['id']),'facts':jobs.get_facts(db,p['id']),'resolved':jobs.get_resolved(db,p['id']),'photos':jobs.get_photo_candidates(db,p['id'],include_excluded=True),'documents':jobs.get_documents(db,p['id']),'readiness':readiness.card_readiness(db,p['id']),'evidence':card_evidence.load(db,p['id'],'hyperx') or {},'presentation':attribute_projection.final_attribute_rows(db,p['id'])}
 out['rows'].append(item);(R/(phase+'.json')).write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8')
 snapshot=latest_source_snapshot(db,p['id'],'hyperx')
 if snapshot:(R/'raw'/(phase+'_'+str(p['id'])+'.html')).write_text(snapshot['content'],encoding='utf8')
 print(p['id'],item['job']['status'],len(item['facts']),item['readiness']['verdict'],flush=True)
