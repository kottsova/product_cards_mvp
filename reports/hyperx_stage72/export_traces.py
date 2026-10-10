"""Export immutable run discovery diagnostics from local SQLite into public artifacts."""
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from product_tool import jobs,discovery_trace
R=Path(__file__).parent;out={}
for phase in ('live_initial','live_final','live_release'):
 db=R/(phase+'.sqlite3');out[phase]={}
 for pid in range(1,11):out[phase][str(pid)]=discovery_trace.for_job(db,jobs.list_jobs(db,pid)[0]['id'])
(R/'discovery_traces.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8')
print({phase:sum(len(events) for events in rows.values()) for phase,rows in out.items()})
