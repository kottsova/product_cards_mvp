"""Actual visible persistent Chrome probe; retains prior access history."""
import sys,json,hashlib,shutil
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from product_tool.census.public_browser import PublicBrowserSession
from product_tool.adapters.access_stop import active_stops
from product_tool.adapters.policy_fetch import read_log
R=Path(__file__).parent
R.mkdir(exist_ok=True)
for name in ('frozen_inputs.json','frozen_inputs.sha256','hyperx_fetch_log.json'):
    path=R/name
    if not path.exists():shutil.copyfile(R.parent/'hyperx_stage72'/name,path)
assert hashlib.sha256((R/'frozen_inputs.json').read_bytes()).hexdigest()==(R/'frozen_inputs.sha256').read_text().strip()
out={'origin':'actual live visible persistent Chrome, not replay','prior_active_stops':active_stops(read_log(R/'hyperx_fetch_log.json')),'pages':[]}
b=PublicBrowserSession(allowed_hosts=('hyperx.com','supportcenter.hyperx.com','files.hyperx.com'),fetch_log_path=R/'hyperx_fetch_log.json',profile_dir=Path('data/hyperx_stage73_chrome_profile'),visible=True)
try:
    b.start()
    for url in ('https://hyperx.com/','https://supportcenter.hyperx.com/'):
        try:
            b.call('goto',url=url);s=b.call('document_snapshot')
            path=R/('probe_'+str(len(out['pages']))+'.html');path.write_text(s.pop('html'),encoding='utf8');s['raw_path']=str(path.relative_to(R));out['pages'].append(s)
            print(url,s['status_code'],s['counts'],flush=True)
        except Exception as e:
            out['pages'].append({'url':url,'error':str(e),'counts':b.counts});print(url,str(e),flush=True)
            break
finally:
    out['session_id']=b.session_id;out['contexts']=1 if b.context else 0
    b.close();(R/'browser_probe.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8')
