"""Actual second live session, same DB/profile; no replay or duplicate evidence."""
import sys,json,hashlib,time
sys.stdout.reconfigure(encoding="utf8")
from pathlib import Path
from datetime import datetime,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from product_tool import jobs,worker,readiness,card_evidence,discovery_trace
from product_tool.adapters.electrolux import ElectroluxAdapter
from product_tool.electrolux_page import MEDIA_HOSTS
from product_tool.census.public_browser import IsolatedPublicBrowserSession as PublicBrowserSession
from product_tool.census.browser_contracts import BrowserBudget
R=Path(__file__).parent;out=R/'release_stability';out.mkdir(exist_ok=True);db=R/'release_live'/'live.sqlite3'
raw=(R/'dataset.json').read_bytes();assert hashlib.sha256(raw).hexdigest()==(R/'dataset.sha256').read_text().strip();rows=[p for p in json.loads(raw)['rows'] if p['id'] in (1,3,4,7,8,10)]
def digest():return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for root in ('product_tool','tests') for p in Path(root).rglob('*') if p.is_file() and p.suffix in {'.py','.html','.js'}}
before_source=digest()
def snapshot(pid):return {'sources':jobs.get_source_pages(db,pid),'facts':jobs.get_facts(db,pid),'resolved':jobs.get_resolved(db,pid),'photos':jobs.get_photo_candidates(db,pid,include_excluded=True),'documents':jobs.get_documents(db,pid),'evidence':card_evidence.load(db,pid,'electrolux') or {},'readiness':readiness.card_readiness(db,pid)}
def signature(s):
 return {'sources':sorted((x['source_key'],x['url']) for x in s['sources']),'resolved':sorted((x['normalized_name'],x.get('selected_value'),x.get('selected_unit'),x['status'],bool(x.get('conflict'))) for x in s['resolved']),'photos':sorted((x['asset_key'],bool(x['selected']),x.get('verified_width'),x.get('verified_height'),x.get('verified_bytes'),x.get('verified_format')) for x in s['photos']),'documents':sorted((x['title'],x['direct_url'],x['language']) for x in s['documents']),'verified_document_bytes':sorted((x['url'],x.get('sha256')) for x in s['evidence'].get('document_inventory',[]) if x.get('verified')),'identity':{k:v for k,v in s['evidence'].get('identity',{}).items() if k not in {'catalog_relations'}},'readiness':(s['readiness']['verdict'],s['readiness']['confirmed_specs'],s['readiness']['conflicts'],s['readiness']['manual_status'])}
def duplicates(s):
 results={}
 for kind,fields in [('sources',('source_key','url')),('photos',('source_key','asset_key')),('documents',('source_key','title','direct_url'))]:
  keys=[tuple(x.get(k) for k in fields) for x in s[kind]];results[kind]=len(keys)-len(set(keys))
 return results
b=PublicBrowserSession(allowed_hosts=MEDIA_HOSTS,fetch_log_path=R/'live_fetch_log.json',profile_dir=Path('data/electrolux_stage78_chrome_profile'),visible=True,use_system_ca=True,budget=BrowserBudget(deadline_seconds=40,operation_timeout_seconds=10),trace_path=out/'browser_timing.jsonl')
a=ElectroluxAdapter(fetch_log_path=R/'live_fetch_log.json',browser_session=b,capture_dir=out/'captures');summary={'origin':'actual second live run; same database and persistent profile, fresh PDP and inventory navigation; no replay','started_at':datetime.now(timezone.utc).isoformat(),'rows':[]}
try:
 b.start();summary.update(contexts=1,session_id=b.session_id,cookies_before_count=b.cookie_count())
 for p in rows:
  before=snapshot(p['id']);a.capture_dir=out/str(p['id'])/'captures';a.capture_dir.mkdir(parents=True,exist_ok=True);jid=jobs.enqueue(db,p['id'],[1,2,3,4,6]);start=time.monotonic();worker.run_once(db,electrolux_adapter_factory=lambda:a);after=snapshot(p['id']);result={'input':p,'observation':'actual live second run','seconds':round(time.monotonic()-start,2),**after,'trace':discovery_trace.for_job(db,jid),'before_signature':signature(before),'after_signature':signature(after),'stable':signature(before)==signature(after),'duplicates':duplicates(after)}
  (out/str(p['id'])/'result.json').write_bytes((json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode());r=after['readiness'];summary['rows'].append({'id':p['id'],'model':p['model'],'live_success':after['evidence'].get('live_success'), 'specs':r['confirmed_specs'],'photos':sum(x['selected'] for x in after['photos']),'manual':r['manual_status'],'readiness':r['verdict'],'stable':result['stable'],'duplicates':result['duplicates'],'seconds':result['seconds']});print(summary['rows'][-1],flush=True)
finally:
 summary.update(cookies_after_count=b.cookie_count() if b.context else 0,navigations=b.total_navigations,finished_at=datetime.now(timezone.utc).isoformat());a.close();b.close();summary.update(context_closed=b.context is None,source_tree_unchanged=before_source==digest());(out/'summary.json').write_bytes((json.dumps(summary,ensure_ascii=False,indent=2)+'\n').encode())
