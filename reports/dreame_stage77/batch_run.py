"""Frozen production live batch and five-category same-context rerun; no URL seeds."""
import sys,json,hashlib,sqlite3,time
from pathlib import Path
from datetime import datetime,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from openpyxl import Workbook
from product_tool import jobs,worker,readiness,card_evidence,discovery_trace,importer
from product_tool.adapters.dreame import DreameAdapter
from product_tool.adapters import access_stop,policy_fetch
from product_tool.census.public_browser import PublicBrowserSession
from product_tool.census.browser_contracts import BrowserBudget
R=Path(__file__).parent;OLD=R.parent/'dreame_stage76'
phase=sys.argv[1] if len(sys.argv)>1 else 'batch_live'
base=R/phase;base.mkdir(exist_ok=True);db=base/'live.sqlite3';assert not db.exists()
raw=(OLD/'dataset.json').read_bytes();sha=hashlib.sha256(raw).hexdigest();assert sha==(OLD/'dataset.sha256').read_text().strip()
control=json.loads((R/'h14_final_control/result.json').read_text(encoding='utf8'));assert control['readiness']['verdict']=='export_ready' and control['evidence']['live_success'] and len(control['evidence']['model_gallery_assets'])>0
rows=json.loads(raw)['rows'];w=Workbook();s=w.active;s.title='Products';s.append(['Бренд','Артикул','Наименование','Категория'])
for p in rows:s.append([p['brand'],p['article'],p['name'],p['category']])
w.save(base/'input.xlsx');preview=importer.preview_xlsx(base/'input.xlsx');assert len(preview.products)==10
jobs.initialize(db);discovery_trace.initialize(db)
with sqlite3.connect(db) as c:
 c.execute("INSERT INTO batches VALUES ('dr77','input.xlsx','Products','{}','2026-10-11')")
 for p,inp in zip(rows,preview.products):
  c.execute("INSERT INTO products (id,batch_id,row_number,name,brand,search_code,alternate_code,category,needs_confirmation,issues_json,original_values_json) VALUES (?,'dr77',?,?,?,?,?,?,0,'[]',?)",(p['id'],inp.row_number,inp.name,inp.brand,inp.search_code,inp.alternate_code,inp.category,json.dumps(inp.original_values,ensure_ascii=False)))
log=R/'dreame_fetch_log.json';before=access_stop.active_stops(policy_fetch.read_log(log));assert not before,before
b=PublicBrowserSession(allowed_hosts=('dreametech.com','dreame.tech','cdn.shopify.com'),fetch_log_path=log,profile_dir=Path('data/dreame_stage77_chrome_profile').resolve(),visible=True,use_system_ca=True,budget=BrowserBudget(deadline_seconds=40,operation_timeout_seconds=10,max_dom_bytes=1000000))
a=DreameAdapter(fetch_log_path=log,browser_session=b)
summary={'phase':phase,'dataset_sha256':sha,'session_id':b.session_id,'actual_live_only':True,'contexts':1,'started_at':datetime.now(timezone.utc).isoformat(),'first':[],'second':[]}
def run(p,passno):
 d=base/('first' if passno==1 else 'second')/str(p['id']);d.mkdir(parents=True,exist_ok=True);a.capture_dir=d/'captures'
 jid=jobs.enqueue(db,p['id'],[1,2,3,4,6]);start=time.monotonic();worker.run_once(db,dreame_adapter_factory=lambda:a)
 v={'id':p['id'],'input':p,'session_id':b.session_id,'seconds':round(time.monotonic()-start,2),'job':jobs.list_jobs(db,p['id'])[0],'sources':jobs.get_source_pages(db,p['id']),'facts':jobs.get_facts(db,p['id']),'resolved':jobs.get_resolved(db,p['id']),'photos':jobs.get_photo_candidates(db,p['id'],include_excluded=True),'documents':jobs.get_documents(db,p['id']),'readiness':readiness.card_readiness(db,p['id']),'evidence':card_evidence.load(db,p['id'],'dreame') or {},'trace':discovery_trace.for_job(db,jid),'total_navigations':b.total_navigations,'active_stops_after':access_stop.active_stops(policy_fetch.read_log(log))}
 (d/'result.json').write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 r={'id':p['id'],'model':p['model'],'pdp':v['evidence'].get('pdp_url'),'live':v['evidence'].get('live_success',False),'specs':v['readiness']['confirmed_specs'],'photos':len(v['evidence'].get('model_gallery_assets',[])),'manual':v['readiness']['manual_status'],'readiness':v['readiness']['verdict'],'gaps':v['readiness']['blocking_gaps'],'seconds':v['seconds'],'navigations':b.total_navigations}
 summary['first' if passno==1 else 'second'].append(r);print(r,flush=True)
 (base/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 return v
try:
 b.start();summary['cookies_before_count']=len(b.context.cookies())
 for p in rows:
  v=run(p,1)
  if v['active_stops_after']:summary['stopped_on_new_access_stop']=True;break
 if len(summary['first'])==10 and all(x['live'] and x['photos'] for x in summary['first']):
  for p in rows:
   if p['id'] not in {1,2,5,8,9,10}:continue
   v=run(p,2)
   if v['active_stops_after']:summary['stopped_on_new_access_stop']=True;break
 summary['cookies_after_count']=len(b.context.cookies());summary['total_navigations']=b.total_navigations
finally:
 b.close();summary['context_closed']=b.context is None;summary['finished_at']=datetime.now(timezone.utc).isoformat();summary['active_stops_after']=access_stop.active_stops(policy_fetch.read_log(log));(base/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
