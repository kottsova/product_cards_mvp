from pathlib import Path
import time,json
from product_tool.adapters.lenovo import LenovoAdapter,support_identity,object_after
from product_tool.adapters.policy_session import record_responses
r=Path('reports/lenovo_stage60');a=LenovoAdapter(fetch_log_path=r/'adapter_baseline_fetch_log.json')
with record_responses(r/'adapter_baseline_responses'):
 d=a.find_source('21ML005BUS',name='ThinkPad T14 Gen 5 Intel',deadline=time.monotonic()+90)
 print(json.dumps({'level':d.match_level,'error':d.error,'attrs':[(x.name,x.value) for x in d.attributes],'report':a.reports},ensure_ascii=True,default=str),flush=True)
 (r/'adapter_baseline_probe.json').write_text(json.dumps(a.reports,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
 if d.url:
  url=d.url.replace('21ml005bus','21mlzzzzus');x=a.http.get(url,timeout=10)
  info=object_after(x.text,r'var\s+ds_productinfo\s*=')
  test={'url':url,'status':x.status_code,'identity':support_identity(info,'21MLZZZZUS'),'description':info.get('Description','')}
  (r/'invalid_mtm_probe.json').write_text(json.dumps(test,indent=2),encoding='utf-8');print(json.dumps(test),flush=True)
