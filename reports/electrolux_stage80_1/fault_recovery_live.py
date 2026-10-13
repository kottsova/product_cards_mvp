"""Injected timeout is synthetic; subsequent recovered official data is live."""
import sys,json,os,sqlite3,time,subprocess
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
sys.stdout.reconfigure(encoding='utf8')
from product_tool import jobs,worker,card_evidence,readiness,discovery_trace
from product_tool.census.public_browser import IsolatedPublicBrowserSession
from product_tool.census.browser_runtime import BrowserRuntime,PlaywrightBrowser
from product_tool.census.browser_contracts import BrowserBudget
from product_tool.electrolux_page import MEDIA_HOSTS
from product_tool.adapters.electrolux import ElectroluxAdapter
R=Path(__file__).parent;out=R/(sys.argv[1] if len(sys.argv)>1 else 'fault_recovery_final');out.mkdir(exist_ok=True)
marker=out/'injected_fault.json';assert not marker.exists()
rows=[x for x in json.loads((R/'dataset.json').read_text(encoding='utf8'))['rows'] if x['id'] in (1,3)]
db=out/'live.sqlite3';jobs.initialize(db);assert not jobs.list_jobs(db,1) and not jobs.list_jobs(db,3)
with sqlite3.connect(db) as c:
 c.execute("INSERT INTO batches VALUES ('fault801','frozen','Products','{}','2026-10-13')")
 for p in rows:
  c.execute("INSERT INTO products (id,batch_id,row_number,name,brand,search_code,alternate_code,category,needs_confirmation,issues_json,original_values_json,identity_json) VALUES (?,'fault801',?,?, 'Electrolux',?,'',?,0,'[]','{}',?)",(p['id'],p['id']+1,p['name'],p['article'],p['category'],json.dumps({'input_configuration':{'region':p['region'],'color':p['input_color']}})))
budget=BrowserBudget(deadline_seconds=40,operation_timeout_seconds=10)
def factory():return PlaywrightBrowser(BrowserRuntime(True,sys.executable),budget,MEDIA_HOSTS,worker_script=R/'injected_real_worker.py')
class FaultSession(IsolatedPublicBrowserSession):
 def invoke(self,command,limit,**args):
  if command=='public_goto' and not marker.exists():limit=min(limit,.8)
  return super().invoke(command,limit,**args)
def process_tree(pid):
 command="Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId,Name | ConvertTo-Json -Compress"
 data=json.loads(subprocess.check_output(['powershell','-NoProfile','-Command',command],text=True));found={pid}
 while True:
  extended=found|{x['ProcessId'] for x in data if x['ParentProcessId'] in found}
  if extended==found:break
  found=extended
 return [x for x in data if x['ProcessId'] in found]
b=FaultSession(allowed_hosts=MEDIA_HOSTS,fetch_log_path=R/'live_fetch_log.json',profile_dir=Path('data/electrolux_stage78_chrome_profile'),visible=True,use_system_ca=True,budget=budget,worker_factory=factory,trace_path=out/'browser_timing.jsonl')
a=ElectroluxAdapter(fetch_log_path=R/'live_fetch_log.json',browser_session=b,capture_dir=out/'captures');summary={}
try:
 with patch.dict(os.environ,{'ELECTROLUX_QUALIFICATION_FAULT_MARKER':str(marker.resolve())}):
  b.start();old_worker=b.worker;old_session=b.session_id;tree=process_tree(old_worker.process.pid)
  assert any(x['Name']=='chrome.exe' for x in tree),tree
  jid=jobs.enqueue(db,1,[1,2,3,4,6]);start=time.monotonic();worker.run_once(db,electrolux_adapter_factory=lambda:a)
  elapsed=time.monotonic()-start;events=discovery_trace.for_job(db,jid)
  failed_event=next(e for e in events if e.get('phase')=='public_goto' and e.get('timeout'))
  assert elapsed<8 and old_worker.process.poll() is not None and b.failed and b.context is None
  remaining=[x for x in tree if process_tree(x['ProcessId'])]
  assert not remaining,remaining
  assert jobs.list_jobs(db,1)[0]['status']=='needs_review'
  summary['injected_timeout']={'origin':'synthetic failure, not live success','seconds':elapsed,'event':failed_event,'context_discarded':True,'owned_process_tree':tree,'remaining_owned_processes':remaining,'job':jobs.list_jobs(db,1)[0]}
  a.capture_dir=out/'recovered_captures';jid=jobs.enqueue(db,3,[1,2,3,4,6]);start=time.monotonic();worker.run_once(db,electrolux_adapter_factory=lambda:a)
  ev=card_evidence.load(db,3,'electrolux');r=readiness.card_readiness(db,3)
  assert ev['live_success'] and not b.failed and b.recoveries==1 and b.session_id!=old_session and r['verdict']=='export_ready'
  result={'input':rows[1],'observation':'actual live after injected timeout recovery','evidence':ev,'readiness':r,'sources':jobs.get_source_pages(db,3),'facts':jobs.get_facts(db,3),'resolved':jobs.get_resolved(db,3),'photos':jobs.get_photo_candidates(db,3),'documents':jobs.get_documents(db,3),'trace':discovery_trace.for_job(db,jid)}
  (out/'recovered_result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
  summary['recovered_job']={'origin':'actual live official data','model':rows[1]['model'],'seconds':time.monotonic()-start,'readiness':r,'new_session':b.session_id,'old_session':old_session,'recoveries':b.recoveries}
finally:
 a.close();b.close();summary['context_closed']=b.context is None
 (R/(out.name+'_summary.json')).write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print({'injected_seconds':summary['injected_timeout']['seconds'],'remaining_processes':len(summary['injected_timeout']['remaining_owned_processes']),'recovered_model':summary['recovered_job']['model'],'recovered_readiness':summary['recovered_job']['readiness']['verdict'],'recovered_specs':summary['recovered_job']['readiness']['confirmed_specs'],'context_closed':summary['context_closed']})
