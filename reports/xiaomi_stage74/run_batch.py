"""Frozen Stage 74 actual-live worker batch; no seeded PDPs, captures or replay transport."""
import hashlib,json,sqlite3,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from product_tool import jobs,worker,readiness,discovery_trace,card_evidence
from product_tool.adapters.xiaomi import XiaomiAdapter
from product_tool.adapters.policy_session import record_responses
R=Path(__file__).parent

def main():
    raw=(R/'dataset.json').read_bytes();assert hashlib.sha256(raw).hexdigest()==(R/'dataset.sha256').read_text().strip()
    rows=json.loads(raw)['rows'];run=sys.argv[1] if len(sys.argv)>1 else 'first_pass';outdir=R/run;outdir.mkdir(exist_ok=True)
    db=outdir/'live.sqlite3';assert not db.exists();jobs.initialize(db);discovery_trace.initialize(db)
    with sqlite3.connect(db) as c:
        c.execute("INSERT INTO batches VALUES ('xm74','Stage 74.xlsx','Products','{}','2026-10-10')")
        for p in rows:
            c.execute("INSERT INTO products (id,batch_id,row_number,name,brand,search_code,alternate_code,category,needs_confirmation,issues_json,original_values_json) VALUES (?,'xm74',?,?,?,?,'',?,0,'[]',?)",(p['id'],p['id']+1,p['name'],p['brand'],p['article'],p['category'],json.dumps(p,ensure_ascii=False)))
    adapter=XiaomiAdapter(fetch_log_path=outdir/'xiaomi_fetch_log.json',capture_dir=outdir/'captures')
    results=[]
    with record_responses(outdir/'http'):
        for p in rows:
            assert hashlib.sha256((R/'dataset.json').read_bytes()).hexdigest()==hashlib.sha256(raw).hexdigest()
            start=time.monotonic();jid=jobs.enqueue(db,p['id'],[1,2,3,4,6]);worker.run_once(db,xiaomi_adapter_factory=lambda:adapter)
            result={'id':p['id'],'input':p,'observation':'actual_live_worker','seconds':round(time.monotonic()-start,2),'job':jobs.list_jobs(db,p['id'])[0],'sources':jobs.get_source_pages(db,p['id']),'facts':jobs.get_facts(db,p['id']),'resolved':jobs.get_resolved(db,p['id']),'photos':jobs.get_photo_candidates(db,p['id']),'documents':jobs.get_documents(db,p['id']),'readiness':readiness.card_readiness(db,p['id']),'evidence':card_evidence.load(db,p['id'],'xiaomi'),'trace':discovery_trace.for_job(db,jid)}
            results.append(result);(outdir/'results.json').write_text(json.dumps({'dataset_sha256':hashlib.sha256(raw).hexdigest(),'rows':results},ensure_ascii=False,indent=2),encoding='utf8')
            print(p['id'],p['model'],result['job']['status'],result['readiness']['confirmed_specs'],result['readiness']['verdict'],result['readiness']['manual_status'],flush=True)
if __name__=='__main__':main()
