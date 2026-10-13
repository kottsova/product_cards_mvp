"""Deterministic timeout -> ordinary worker job -> fresh context/re-run."""
import json,os,sys,sqlite3,tempfile,time,unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
from product_tool import jobs,worker,card_evidence,discovery_trace
from product_tool.census.browser_runtime import BrowserRuntime,PlaywrightBrowser,BrowserFailure
from product_tool.census.browser_contracts import BrowserBudget
from product_tool.census.public_browser import IsolatedPublicBrowserSession
from product_tool.adapters.electrolux import ElectroluxAdapter
from product_tool.adapters.common import SourceDocument
from product_tool.adapters import policy_fetch,access_stop

FIXTURE=Path(__file__).parent/'fixtures/electrolux_stall_worker.py'
class FastFaultSession(IsolatedPublicBrowserSession):
 def invoke(self,command,limit,**args):
  if command=='public_goto':limit=min(limit,.7)
  return super().invoke(command,limit,**args)
class NoInventoryAdapter(ElectroluxAdapter):
 def find_inventory(self,*args):return {'relations':[],'requested_relation':'unproven'}

def database(root):
 db=root/'test.sqlite3';jobs.initialize(db);discovery_trace.initialize(db)
 with closing(sqlite3.connect(db)) as c,c:
  c.execute("INSERT INTO batches VALUES ('fault','offline.xlsx','Products','{}','2026-10-13')")
  for pid in (1,2):
   c.execute("INSERT INTO products (id,batch_id,row_number,name,brand,search_code,alternate_code,category,needs_confirmation,issues_json,original_values_json,identity_json) VALUES (?,'fault',?,'Electrolux EOF6P46X','Electrolux','EOF6P46X','','Духовые шкафы',0,'[]','{}','{}')",(pid,pid+1))
 return db

class Stage801(unittest.TestCase):
 def make_session(self,root):
  budget=BrowserBudget(operation_timeout_seconds=10)
  def factory():return PlaywrightBrowser(BrowserRuntime(True,sys.executable),budget,('electrolux.co.uk',),worker_script=FIXTURE)
  return FastFaultSession(allowed_hosts=('electrolux.co.uk',),fetch_log_path=root/'fetch.json',profile_dir=root/'profile',visible=True,budget=budget,worker_factory=factory)
 def test_timeout_record_and_normal_worker_next_job_and_rerun(self):
  with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'ELECTROLUX_QUALIFICATION_FAULT_DIR':tmp}):
   root=Path(tmp);db=database(root);b=self.make_session(root);external=[];dealer=[]
   class External:
    def search_provider(self,*args):external.append(args);raise AssertionError('Technical failure is not an official miss')
   a=NoInventoryAdapter(fetch_log_path=root/'fetch.json',browser_session=b,capture_dir=root/'captures',external_search=External())
   class Dealer:
    def find_source(self,*a,**kw):dealer.append(kw);raise AssertionError('Must not mask technical failure')
   try:
    b.start();first_worker=b.worker;first_session=b.session_id
    bad=jobs.enqueue(db,1,[1,2,3]);good=jobs.enqueue(db,2,[1,2,3]);start=time.monotonic()
    self.assertTrue(worker.run_once(db,electrolux_adapter_factory=lambda:a,dns_adapter_factory=Dealer))
    self.assertLess(time.monotonic()-start,5);self.assertIsNotNone(first_worker.process.poll())
    self.assertTrue(b.failed);self.assertIsNone(b.context);self.assertIsNone(b.status);self.assertEqual(b.url,'')
    self.assertEqual(jobs.list_jobs(db,1)[0]['status'],'needs_review')
    self.assertIn('technical_failure',card_evidence.load(db,1,'electrolux'))
    self.assertEqual(external,[]);self.assertEqual(dealer,[])
    trace=discovery_trace.for_job(db,bad)
    event=next(e for e in trace if e.get('phase')=='public_goto' and e.get('timeout'))
    self.assertEqual(event['url'],'https://www.electrolux.co.uk/')
    self.assertEqual(event['exception'],'driver_wall_timeout');self.assertEqual(event['state'],'end')
    self.assertEqual(event['job_id'],bad)
    stack=(root/'electrolux_browser_timing.stack.log').read_text()
    self.assertIn('Timeout',stack);self.assertIn('electrolux_stall_worker.py',stack)
    self.assertTrue(worker.run_once(db,electrolux_adapter_factory=lambda:a))
    self.assertFalse(b.failed);self.assertNotEqual(b.session_id,first_session);self.assertEqual(b.recoveries,1)
    self.assertGreater(len(jobs.get_resolved(db,2)),20);self.assertEqual(jobs.list_jobs(db,2)[0]['status'],'done')
    self.assertTrue(any(e.get('phase')=='session_recovery' and e.get('state')=='end' for e in discovery_trace.for_job(db,good)))
    jobs.enqueue(db,2,[1,2,3]);self.assertTrue(worker.run_once(db,electrolux_adapter_factory=lambda:a))
    self.assertEqual(b.recoveries,1)
    self.assertEqual(len(jobs.get_source_pages(db,2)),1)
    # Cleanup is still performed when the product deadline has expired.
    b.deadline=0;b.close();self.assertIsNone(b.context)
    contexts=[json.loads(x) for x in (root/'contexts.jsonl').read_text().splitlines()]
    created=[x['id'] for x in contexts if x.get('created')]
    self.assertEqual(len(created),2);self.assertNotEqual(*created)
    self.assertTrue(any(x.get('closed') and x['id']==created[-1] for x in contexts))
    telemetry=[json.loads(x) for x in b.trace_path.read_text().splitlines()]
    phases={x.get('source_type') for x in telemetry if x.get('provider')=='timing'}
    self.assertTrue({'job_start','job_finish','discovery','extraction','documents','photos','persistence'}<=phases)
   finally:b.close()
 def test_recovery_preserves_access_stops_and_never_navigates_stopped_host(self):
  with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'ELECTROLUX_QUALIFICATION_FAULT_DIR':tmp}):
   root=Path(tmp);b=self.make_session(root)
   try:
    b.start()
    with self.assertRaisesRegex(BrowserFailure,'driver_wall_timeout'):b.call('goto',url='https://www.electrolux.co.uk/')
    policy_fetch.record_stop(root/'fetch.json','www.electrolux.co.uk',access_stop.RATE_LIMIT)
    before=(root/'fetch.json').read_bytes();b.recover_for_next_product()
    with self.assertRaisesRegex(BrowserFailure,'host_stopped'):b.call('goto',url='https://www.electrolux.co.uk/')
    self.assertEqual((root/'fetch.json').read_bytes(),before)
   finally:b.close()
 def test_recovery_budget_is_bounded(self):
  with tempfile.TemporaryDirectory() as tmp:
   b=self.make_session(Path(tmp));b.failed=True;b.recoveries=1
   with self.assertRaisesRegex(BrowserFailure,'session_recovery_budget_exhausted'):b.recover_for_next_product()
   self.assertIsNone(b.worker.process)
 def test_observed_rate_stop_survives_timeout_before_dom_snapshot(self):
  with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'ELECTROLUX_QUALIFICATION_FAULT_DIR':tmp,'ELECTROLUX_QUALIFICATION_RATE_BEFORE_STALL':'1'}):
   root=Path(tmp);b=self.make_session(root)
   try:
    b.start()
    with self.assertRaisesRegex(BrowserFailure,'driver_wall_timeout'):b.call('goto',url='https://www.electrolux.co.uk/')
    self.assertIn('www.electrolux.co.uk',access_stop.active_stops(policy_fetch.read_log(root/'fetch.json')))
    b.recover_for_next_product()
    with self.assertRaisesRegex(BrowserFailure,'host_stopped'):b.call('goto',url='https://www.electrolux.co.uk/')
   finally:b.close()
 def test_worker_cli_controlled_mode_wires_bounded_session_and_cleans_up(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)
   with patch.object(sys,'argv',['worker','--data-dir',str(root),'--once','--electrolux-browser-profile',str(root/'profile')]),patch('product_tool.census.public_browser.IsolatedPublicBrowserSession') as session,patch('product_tool.adapters.electrolux.ElectroluxAdapter') as adapter,patch.object(worker,'run_once',return_value=False) as once,patch.object(worker.logging,'basicConfig'):
    worker.main();session.return_value.start.assert_called_once();session.return_value.close.assert_called_once()
    kwargs=session.call_args.kwargs;self.assertTrue(kwargs['visible']);self.assertTrue(kwargs['use_system_ca'])
    self.assertEqual(once.call_args.kwargs['electrolux_adapter_factory'](),adapter.return_value)
    self.assertNotIn('trace_path',kwargs) # Automatic persistent diagnostics path.

if __name__=='__main__':unittest.main()
