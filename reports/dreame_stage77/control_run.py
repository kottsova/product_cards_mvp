"""One frozen H14 Pro input through ordinary worker, fresh persistent Chrome DOM."""
import sys,json,hashlib,sqlite3,time,shutil,os
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
phase=sys.argv[1] if len(sys.argv)>1 else 'h14_control'
outdir=R/phase;outdir.mkdir(parents=True,exist_ok=True);db=outdir/'live.sqlite3';assert not db.exists()
raw=(OLD/'dataset.json').read_bytes();sha=hashlib.sha256(raw).hexdigest();assert sha==(OLD/'dataset.sha256').read_text().strip()
p=next(x for x in json.loads(raw)['rows'] if x['id']==5)
w=Workbook();s=w.active;s.title='Products';s.append(['Бренд','Артикул','Наименование','Категория']);s.append([p['brand'],p['article'],p['name'],p['category']]);w.save(outdir/'input.xlsx')
preview=importer.preview_xlsx(outdir/'input.xlsx');assert len(preview.products)==1;inp=preview.products[0]
jobs.initialize(db);discovery_trace.initialize(db)
with sqlite3.connect(db) as c:
    c.execute("INSERT INTO batches VALUES ('dr77','input.xlsx','Products','{}','2026-10-11')")
    c.execute("INSERT INTO products (id,batch_id,row_number,name,brand,search_code,alternate_code,category,needs_confirmation,issues_json,original_values_json) VALUES (5,'dr77',?,?,?,?,?,?,0,'[]',?)",(inp.row_number,inp.name,inp.brand,inp.search_code,inp.alternate_code,inp.category,json.dumps(inp.original_values,ensure_ascii=False)))
log=R/'dreame_fetch_log.json'
if not log.exists():shutil.copyfile(OLD/'final_live/dreame_fetch_log.json',log)
prior=policy_fetch.read_log(log);active=access_stop.active_stops(prior);assert 'global.dreametech.com' not in active,active
profile=Path('data/dreame_stage77_chrome_profile').resolve()
browser=PublicBrowserSession(allowed_hosts=('dreametech.com','dreame.tech','cdn.shopify.com'),fetch_log_path=log,profile_dir=profile,visible=True,use_system_ca=True,budget=BrowserBudget(deadline_seconds=40,operation_timeout_seconds=10,max_dom_bytes=1000000))
adapter=DreameAdapter(fetch_log_path=log,capture_dir=outdir/'captures',browser_session=browser)
out={'phase':phase,'input':p,'dataset_sha256':sha,'origin':'ordinary run_once; fresh visible persistent Chrome DOM; no known PDP seed or capture replay','started_at':datetime.now(timezone.utc).isoformat(),'active_stops_before':active,'profile_path':str(profile),'channel':'chrome','visible':True,'browser_bridge_error':'CUA kernel exited code=1: windows sandbox helper_unknown_error, setup refresh had errors; before browser navigation','session_id':browser.session_id,'contexts':0}
try:
    browser.start();out['contexts']=1;out['browser_started']=True;out['cookies_before_count']=len(browser.context.cookies())
    jid=jobs.enqueue(db,5,[1,2,3,4,6]);start=time.monotonic();worker.run_once(db,dreame_adapter_factory=lambda:adapter)
    out.update(seconds=round(time.monotonic()-start,2),job=jobs.list_jobs(db,5)[0],sources=jobs.get_source_pages(db,5),facts=jobs.get_facts(db,5),resolved=jobs.get_resolved(db,5),photos=jobs.get_photo_candidates(db,5,include_excluded=True),documents=jobs.get_documents(db,5),readiness=readiness.card_readiness(db,5),evidence=card_evidence.load(db,5,'dreame') or {},trace=discovery_trace.for_job(db,jid),cookies_after_count=len(browser.context.cookies()),total_navigations=browser.total_navigations)
    browser.page.screenshot(path=str(outdir/'last_page.png'))
except Exception as exc:
    out.update(error_type=type(exc).__name__,error=str(exc));raise
finally:
    out['active_stops_after']=access_stop.active_stops(policy_fetch.read_log(log));browser.close();out['context_closed']=browser.context is None;out['finished_at']=datetime.now(timezone.utc).isoformat();(outdir/'result.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print({k:out.get(k) for k in ('phase','browser_started','contexts','session_id','seconds','total_navigations','readiness','active_stops_after')},flush=True)
