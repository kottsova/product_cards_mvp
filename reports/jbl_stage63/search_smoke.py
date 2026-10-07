from pathlib import Path
import json,time
from product_tool.adapters.jbl import JBLAdapter,queries
r=Path('reports/jbl_stage63');trace=[];a=JBLAdapter(fetch_log_path=r/'search_fetch.json',trace_callback=trace.append)
start=time.monotonic(); candidates=list(a.shared_search(queries('JBLT520BTBLKEU','JBL Tune 520BT'),deadline=start+45))
result={'duration_seconds':round(time.monotonic()-start,2),'queries':queries('JBLT520BTBLKEU','JBL Tune 520BT'),'candidates':[vars(x) for x in candidates],'trace':trace,'contract':'Existing LGBrowserSearch/old-parser provider; candidate URL alone is not model/photo proof'}
(r/'external_search_smoke.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str),encoding='utf-8');print(json.dumps({'candidates':len(candidates),'trace_count':len(trace),'duration_seconds':result['duration_seconds']}),flush=True)
