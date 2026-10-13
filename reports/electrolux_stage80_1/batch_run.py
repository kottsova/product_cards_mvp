"""Frozen Excel -> ordinary run_once -> actual live official Electrolux evidence."""
import sys,json,hashlib,sqlite3,time
sys.stdout.reconfigure(encoding="utf8")
from pathlib import Path
from datetime import datetime,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from openpyxl import Workbook
from product_tool import importer,jobs,worker,storage,readiness,card_evidence,discovery_trace
from product_tool.adapters.electrolux import ElectroluxAdapter
from product_tool.census.public_browser import IsolatedPublicBrowserSession as PublicBrowserSession
from product_tool.census.browser_contracts import BrowserBudget
R=Path(__file__).parent;raw=(R/'dataset.json').read_bytes();sha=hashlib.sha256(raw).hexdigest();assert sha==(R/'dataset.sha256').read_text().strip();all_rows=json.loads(raw)['rows'];rows=[p for p in all_rows if not sys.argv[2:] or str(p['id']) in sys.argv[2:]]
def source_digest():return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for root in ('product_tool','tests') for p in Path(root).rglob('*') if p.is_file() and p.suffix in {'.py','.html','.js'}}
source_before=source_digest()
phase=sys.argv[1] if len(sys.argv)>1 else 'first_live';out=R/phase;out.mkdir(exist_ok=True);db=out/'live.sqlite3'
assert not db.exists() or not jobs.list_jobs(db)
import faulthandler
stack_log=(out/'runtime_stack.log').open('w',encoding='utf8');faulthandler.dump_traceback_later(60,repeat=True,file=stack_log)
w=Workbook();s=w.active;s.title='Products';s.append(['Бренд','Артикул','Наименование','Категория','Регион','Цвет'])
for p in rows:s.append([p['brand'],p['article'],p['name'],p['category'],p['region'],p['input_color']])
w.save(out/'input.xlsx');preview=importer.preview_xlsx(out/'input.xlsx');assert len(preview.products)==len(rows);jobs.initialize(db);discovery_trace.initialize(db)
with sqlite3.connect(db) as c:
 c.execute("INSERT INTO batches VALUES ('el801','input.xlsx','Products','{}','2026-10-13')")
 for row,p in zip(rows,preview.products):
  original=p.original_values
  c.execute("INSERT INTO products (id,batch_id,row_number,name,brand,search_code,alternate_code,category,needs_confirmation,issues_json,original_values_json,identity_json) VALUES (?,'el801',?,?,?,?,?,?,0,'[]',?,?)",(row['id'],p.row_number,p.name,p.brand,p.search_code,p.alternate_code,p.category,json.dumps(original,ensure_ascii=False),json.dumps({'input_configuration':{'region':row['region'],'color':row['input_color']}})))
log=R/'live_fetch_log.json';b=PublicBrowserSession(allowed_hosts=('electrolux.co.uk','electrolux.ie','electrolux.se','electrolux.de','electrolux.pl','electrolux.com','electroluxgroup.eu','electrolux.bynder.com','electrolux-ui.com'),fetch_log_path=log,profile_dir=Path('data/electrolux_stage78_chrome_profile'),visible=True,use_system_ca=True,budget=BrowserBudget(deadline_seconds=40,operation_timeout_seconds=10),trace_path=out/'browser_timing.jsonl')
a=ElectroluxAdapter(fetch_log_path=log,browser_session=b,capture_dir=out/'captures');summary={'phase':phase,'origin':'actual live ordinary worker; fresh PDP navigation, same-context live catalog cache; no capture/replay injection','dataset_sha256':sha,'started_at':datetime.now(timezone.utc).isoformat(),'rows':[]}
try:
 b.start();summary.update(contexts=1,session_id=b.session_id,cookies_before_count=b.cookie_count())
 for p in rows:
  a.capture_dir=out/str(p['id'])/'captures';a.capture_dir.mkdir(parents=True,exist_ok=True);jid=jobs.enqueue(db,p['id'],[1,2,3,4,6]);start=time.monotonic();worker.run_once(db,electrolux_adapter_factory=lambda:a)
  result={'input':p,'observation':'actual live','seconds':round(time.monotonic()-start,2),'job':jobs.list_jobs(db,p['id'])[0],'sources':jobs.get_source_pages(db,p['id']),'facts':jobs.get_facts(db,p['id']),'resolved':jobs.get_resolved(db,p['id']),'photos':jobs.get_photo_candidates(db,p['id'],include_excluded=True),'documents':jobs.get_documents(db,p['id']),'evidence':card_evidence.load(db,p['id'],'electrolux') or {},'readiness':readiness.card_readiness(db,p['id']),'trace':discovery_trace.for_job(db,jid)}
  (out/str(p['id'])/'result.json').write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode('utf8'));r=result['readiness'];summary['rows'].append({'id':p['id'],'model':p['model'],'live_success':result['evidence'].get('live_success',False),'specs':r.get('confirmed_specs',0),'photos':sum(x['selected'] for x in result['photos']),'manual':r['manual_status'],'readiness':r['verdict'],'gaps':r['blocking_gaps'],'seconds':result['seconds']});print(summary['rows'][-1],flush=True)
finally:
 summary.update(cookies_after_count=b.cookie_count() if b.context else 0,navigations=b.total_navigations,finished_at=datetime.now(timezone.utc).isoformat());a.close();b.close();summary['context_closed']=b.context is None;faulthandler.cancel_dump_traceback_later();stack_log.close();summary['source_tree_unchanged']=source_before==source_digest();summary['source_manifest']=source_before;(out/'summary.json').write_bytes((json.dumps(summary,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
