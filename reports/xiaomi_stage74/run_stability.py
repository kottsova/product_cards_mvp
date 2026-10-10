"""Independent actual-live repeat on five frozen rows; preserve the first 10-row snapshot."""
import sys,json,hashlib,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from product_tool import jobs,worker,readiness,card_evidence,discovery_trace
from product_tool.adapters.xiaomi import XiaomiAdapter
from product_tool.adapters.policy_session import record_responses
R=Path(__file__).parent;raw=(R/'dataset.json').read_bytes();assert hashlib.sha256(raw).hexdigest()==(R/'dataset.sha256').read_text().strip()
db=R/'verified_live/live.sqlite3';out=R/'stability';out.mkdir(exist_ok=True);assert not (out/'results.json').exists()
adapter=XiaomiAdapter(fetch_log_path=out/'xiaomi_fetch_log.json',capture_dir=out/'captures');results=[]
with record_responses(out/'http'):
    for p in json.loads(raw)['rows']:
        if p['id'] not in [1,2,3,6,9]:continue
        jid=jobs.enqueue(db,p['id'],[1,2,3,4,6]);worker.run_once(db,xiaomi_adapter_factory=lambda:adapter)
        result={'id':p['id'],'input':p,'observation':'actual_live_worker','job':jobs.list_jobs(db,p['id'])[0],'sources':jobs.get_source_pages(db,p['id']),'facts':jobs.get_facts(db,p['id']),'resolved':jobs.get_resolved(db,p['id']),'photos':jobs.get_photo_candidates(db,p['id']),'documents':jobs.get_documents(db,p['id']),'readiness':readiness.card_readiness(db,p['id']),'evidence':card_evidence.load(db,p['id'],'xiaomi'),'trace':discovery_trace.for_job(db,jid)}
        results.append(result);(out/'results.json').write_text(json.dumps({'dataset_sha256':hashlib.sha256(raw).hexdigest(),'rows':results},ensure_ascii=False,indent=2),encoding='utf8');print(p['id'],result['job']['status'],result['readiness']['confirmed_specs'],result['readiness']['manual_status'],[d['language'] for d in result['documents']],flush=True)
