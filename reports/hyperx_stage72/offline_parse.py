"""Offline parser/worker controls on saved live_final bytes. Never live success."""
import sys,json,hashlib,sqlite3,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from product_tool import jobs,worker,readiness,card_evidence,discovery_trace
from product_tool.adapters.hyperx import HyperXAdapter
from product_tool.adapters.dns import DnsAdapter
from product_tool.hyperx_page import refine_page
R=Path(__file__).parent
raw=(R/'frozen_inputs.json').read_bytes();assert hashlib.sha256(raw).hexdigest()==(R/'frozen_inputs.sha256').read_text().strip()
rows=json.loads(raw)['rows'];phase='offline_parser';db=R/(phase+'.sqlite3');assert not db.exists()
jobs.initialize(db)
with sqlite3.connect(db) as c:
 c.execute("INSERT INTO batches VALUES ('offline72','offline replay','Products','{}','2026-10-10')")
 for p in rows:c.execute("INSERT INTO products (batch_id,row_number,name,brand,search_code,alternate_code,category,needs_confirmation,issues_json,original_values_json) VALUES ('offline72',?,?,'HyperX',?,'',?,0,'[]','{}')",(p['id'],p['name'],p['article'],p['category']))
class Replay(HyperXAdapter):
 def find_source(self,code,*,name='',category='',deadline):
  row=next(r for r in rows if r['article']==code);path=R/'raw'/f"live_final_{row['id']}.html";html=path.read_text(encoding='utf8')
  saved=json.loads((R/'live_final.json').read_text(encoding='utf8'))['rows'][row['id']-1]
  url=next(s['url'] for s in saved['sources'] if s['source_key']=='hyperx')
  doc,ev=refine_page(self.parse_page(html,url,catalog_code=code),html,url,code,name)
  ev.update(provenance='offline parser on saved live_final response; not new live',response_sha256=hashlib.sha256(path.read_bytes()).hexdigest());self.reports[code]=ev
  return doc
 def find_documents(self,code,*,deadline):return [],'Offline parser: manual search not performed'
adapter=Replay(discovery_enabled=True,urls={},fetch_log_path=R/'offline_no_network_log.json')
out={'origin':'offline parser/worker on previously saved actual live_final pages; NO live success','input_sha256':hashlib.sha256(raw).hexdigest(),'rows':[]}
for p in rows:
 jid=jobs.enqueue(db,p['id'],[1,2,3,4,6]);worker.run_once(db,hyperx_adapter_factory=lambda:adapter,dns_adapter_factory=lambda:DnsAdapter(urls={},document_urls={}))
 ev=card_evidence.load(db,p['id'],'hyperx') or {};out['rows'].append({'id':p['id'],'readiness':readiness.card_readiness(db,p['id']),'evidence':ev,'resolved':jobs.get_resolved(db,p['id']),'photos':jobs.get_photo_candidates(db,p['id'])})
 (R/(phase+'.json')).write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8')
 print(p['id'],out['rows'][-1]['readiness']['confirmed_specs'],out['rows'][-1]['readiness']['verdict'],flush=True)
assert adapter.request_count==0 and not (R/'offline_no_network_log.json').exists()
