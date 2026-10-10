"""Frozen Stage72 inputs; actual fresh PDP DOM in one persistent context."""
import sys,json,hashlib,time,sqlite3
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from product_tool import jobs,worker,readiness,card_evidence,discovery_trace
from product_tool.adapters.hyperx import HyperXAdapter
from product_tool.census.public_browser import PublicBrowserSession
R=Path(__file__).parent;phase=sys.argv[1];db=R/(phase+'.sqlite3');assert not db.exists()
raw=(R/'frozen_inputs.json').read_bytes();assert hashlib.sha256(raw).hexdigest()==(R/'frozen_inputs.sha256').read_text().strip()
rows=json.loads(raw)['rows']
if phase=='stability_actual':rows=[p for p in rows if p['id'] in {1,4,6,8,9}]
# The second run covers all ten, including the corrected wired headset block.
reuse=phase in {'live_release','second_live','corrected_live','stable_live','release_actual','stability_actual'}
if reuse:
    previous={'live_release':'live_final','second_live':'live_release','corrected_live':'live_release','stable_live':'corrected_live','release_actual':'stable_live','stability_actual':'release_actual'}[phase]
    source=sqlite3.connect(R/(previous+'.sqlite3'));target=sqlite3.connect(db)
    try:source.backup(target)
    finally:source.close();target.close()
else:
    jobs.initialize(db)
    with sqlite3.connect(db) as c:
        c.execute("INSERT INTO batches VALUES ('hx73','HyperX Stage 73.xlsx','Products','{}','2026-10-10')")
        for p in rows:c.execute("INSERT INTO products (batch_id,row_number,name,brand,search_code,alternate_code,category,needs_confirmation,issues_json,original_values_json) VALUES ('hx73',?,?, 'HyperX',?, '',?,0,'[]',?)",(p['id'],p['name'],p['article'],p['category'],json.dumps(p)))
discovery_trace.initialize(db)
b=PublicBrowserSession(allowed_hosts=('hyperx.com','supportcenter.hyperx.com','files.hyperx.com'),fetch_log_path=R/'hyperx_fetch_log.json',profile_dir=Path('data/hyperx_stage73_chrome_profile'),visible=True,resource_hosts=('prod-care-community-cdn.sprinklr.com','prod.cdata.app.sprinklr.com'),allow_readonly_graphql=True,readonly_graphql_paths=('/schema/community',),use_system_ca=True)
adapter=HyperXAdapter(discovery_enabled=True,browser_session=b,fetch_log_path=R/'hyperx_fetch_log.json',capture_dir=R/'captures')
out={'phase':phase,'origin':'actual fresh official DOM in visible persistent Chrome; no PDP replay','input_sha256':hashlib.sha256(raw).hexdigest(),'session_id':b.session_id,'contexts':1,'rows':[]}
try:
    b.start()
    for pid,p in enumerate(rows,1):
        if reuse:pid=p['id']
        jid=jobs.enqueue(db,pid,[1,2,3,4,6]);start=time.monotonic()
        worker.run_once(db,hyperx_adapter_factory=lambda:adapter)
        item={'id':p['id'],'product_id':pid,'input':p,'elapsed':time.monotonic()-start,'job':jobs.list_jobs(db,pid)[0],'sources':jobs.get_source_pages(db,pid),'facts':jobs.get_facts(db,pid),'resolved':jobs.get_resolved(db,pid),'photos':jobs.get_photo_candidates(db,pid,include_excluded=True),'documents':jobs.get_documents(db,pid),'readiness':readiness.card_readiness(db,pid),'evidence':card_evidence.load(db,pid,'hyperx') or {},'trace':discovery_trace.for_job(db,jid)}
        out['rows'].append(item);(R/(phase+'.json')).write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8')
        print(p['id'],item['job']['status'],item['readiness']['confirmed_specs'],item['readiness']['verdict'],item['evidence'].get('reason'),flush=True)
finally:
    out['total_navigations']=b.total_navigations;b.close();(R/(phase+'.json')).write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8')
