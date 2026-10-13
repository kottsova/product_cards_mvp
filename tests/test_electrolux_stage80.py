"""Bounded driver protocol and identity-scoped Electrolux evidence."""
import json,subprocess,sys,tempfile,time,unittest
from pathlib import Path
from product_tool.census.browser_runtime import PlaywrightBrowser,BrowserRuntime,BrowserFailure
from product_tool.census.browser_contracts import BrowserBudget
from product_tool.census.public_browser import IsolatedPublicBrowserSession
from product_tool.electrolux_page import parse,evidence_graph,inventory,revision_owner
from tests.test_electrolux_stage79 import fixture,EOD,IE,SHOP

class Stage80(unittest.TestCase):
 def test_unresponsive_driver_cannot_hold_caller(self):
  b=PlaywrightBrowser(BrowserRuntime(True,sys.executable),BrowserBudget(),('example.test',))
  b.process=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
  start=time.monotonic()
  try:
   with self.assertRaises(BrowserFailure):b.call('goto',wall_timeout=.15,url='https://example.test/')
   self.assertLess(time.monotonic()-start,3);self.assertIsNotNone(b.process.poll())
  finally:b.close()
 def test_expired_product_does_not_navigate(self):
  with tempfile.TemporaryDirectory() as tmp:
   b=IsolatedPublicBrowserSession(trace_path=Path(tmp)/'timing.jsonl',allowed_hosts=('example.test',),fetch_log_path=Path(tmp)/'fetch.json')
   b.deadline=0
   with self.assertRaisesRegex(BrowserFailure,'product_budget_exhausted'):b.call('goto',url='https://example.test/')
   self.assertIsNone(b.worker.process)
 def test_stalled_session_is_not_retried_or_cleared(self):
  with tempfile.TemporaryDirectory() as tmp:
   b=IsolatedPublicBrowserSession(trace_path=Path(tmp)/'timing.jsonl',allowed_hosts=('example.test',),fetch_log_path=Path(tmp)/'fetch.json');b.failed=True
   with self.assertRaisesRegex(BrowserFailure,'session_unavailable'):b.snapshot()
   self.assertIsNone(b.worker.process)
 def test_duplicate_fullspec_values_have_same_parent_and_distinct_paths(self):
  _,ev=parse(fixture(IE),IE,'EFI61141B','','IE')
  rows=next(c['rows'] for c in ev['source_field_collisions'] if c['label']=='Push Button Functions')
  self.assertEqual(rows[0]['parent_context'],rows[1]['parent_context'])
  self.assertNotEqual(rows[0]['structured_path'],rows[1]['structured_path'])
  self.assertNotEqual(rows[0]['value'],rows[1]['value'])
 def test_inventory_does_not_create_revision_spec_or_document_equivalence(self):
  _,ev=parse(fixture(EOD),EOD,'EOD6C46K2','94949957800','UK')
  ev['pnc_inventory']=inventory(fixture(SHOP),SHOP,'EOD6C46K2','94949957800')
  ev['requested_revision']={'confirmed':True,'url':'https://shop.electrolux.co.uk/search?pnc=94949957800'}
  graph=evidence_graph(ev,EOD)
  self.assertEqual(len([e for e in graph['edges'] if e['evidence_type']=='inventory']),2)
  self.assertEqual(next(e['relation'] for e in graph['edges'] if e['evidence_type']=='specifications/documents'),'unknown')
  self.assertFalse(any(d['identity_verified'] for d in ev['document_inventory']))
  self.assertTrue(any(e['relation']=='model_shared' for e in graph['edges']))
  self.assertTrue(all(e['relation']=='unknown' for e in graph['edges'] if e['evidence_type']=='specification' and e['label']=='Net Weight (Kg)'))
 def test_graph_exact_base_pnc_never_fabricates_revision(self):
  _,ev=parse(fixture(EOD),EOD,'EOD6C46K2','949499578','UK')
  graph=evidence_graph(ev,EOD)
  self.assertFalse(any(e['relation']=='revision_specific' for e in graph['edges']))
  self.assertTrue(any(e['relation']=='exact_pnc' and e['evidence_type']=='specification' for e in graph['edges']))

if __name__=='__main__':unittest.main()
