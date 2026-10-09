"""Corrected extraction/resolution on genuine captures, explicitly NOT live discovery."""
import json,hashlib
from pathlib import Path
from product_tool import storage,jobs,worker,readiness,card_evidence,discovery_trace
from product_tool.adapters.common import SourceDocument,ProductDocument,utc_now
from product_tool.razer_page import parse_page
R=Path(__file__).parent;raw=(R/'frozen_inputs.json').read_bytes();assert hashlib.sha256(raw).hexdigest()==(R/'frozen_inputs.sha256').read_text().strip();dataset=json.loads(raw)['rows'];db=R/'corrected_replay_release.sqlite3';assert not db.exists();jobs.initialize(db);discovery_trace.initialize(db)
first=json.loads((R/'first_pass.json').read_text(encoding='utf8'))['rows'];second=json.loads((R/'corrected_live.json').read_text(encoding='utf8'))['rows'];live={r['id']:r for r in first}
for r in second:
 if r['evidence'].get('identity',{}).get('model_confirmed'):live[r['id']]=r
class Replay:
 def __init__(self,id):self.row=live[id];self.reports={};self.trace_callback=None
 def find_source(self,article,*,name,category,deadline):
  previous=self.row['evidence'];proof=next((p for p in reversed(previous.get('proofs',[])) if p['provider']=='live_browser' and '/answers/detail/' in p['url']),None)
  if proof:
   raw=(R/'captures'/proof['file']).read_bytes();assert hashlib.sha256(raw).hexdigest()==proof['sha256'];doc,ev=parse_page(raw.decode('utf8'),proof['url'],article,name,category)
  else:doc=SourceDocument('razer_model','Razer Official','',error='No captured exact model page; no discovery simulated');ev={'identity':{'model_relation':'unproven'},'raw_specs':[],'accepted_specs':[],'rejected_specs':[],'photos':[],'exact_photo_assets':[]}
  ev.update(manuals=previous.get('manuals',[]),verified_documents=previous.get('verified_documents',[]),manual_status=previous.get('manual_status','Не проверена'),requested_configuration=dataset[self.row['id']-1]['configuration'],proofs=[proof] if proof else [],observation='verified_capture_replay',live_discovery_not_simulated=True)
  self.reports[article]=ev;self.trace_callback({'event':'razer_capture_replay','timestamp':utc_now(),'provider':'verified_capture_replay','query':article,'url':doc.url,'source_type':'support','accepted':doc.match_level=='model_confirmed','reason':'Saved bytes and hash checked; not a live discovery result','identity_relation':ev['identity'].get('model_relation','unproven')});return doc
 def find_documents(self,doc,article):
  ev=self.reports[article];result=[]
  for d in ev['manuals']:
   if not d.get('verified'):continue
   data=(R/'captures'/d['file']).read_bytes();assert hashlib.sha256(data).hexdigest()==d['sha256'];result.append(ProductDocument(d['title'],'Русский','','',d['url'],doc.url,article,ev['identity'].get('model',''),doc.url,True))
  return result
class NoDealer:
 def find_source(self,*a,**k):return SourceDocument('dns','DNS','',error='Replay: dealer network not executed')
with storage._connection(db) as c:
 c.execute('INSERT INTO batches VALUES (?,?,?,?,?)',('rz70','Razer extraction replay','Products','{}',storage._now()))
 for row in dataset:c.execute('INSERT INTO products (batch_id,row_number,name,brand,search_code,alternate_code,category,needs_confirmation,issues_json,original_values_json) VALUES (?,?,?,?,?,?,?,?,?,?)',('rz70',row['id'],row['name'],'Razer',row['article'],'',row['category'],0,'[]',json.dumps(row)))
out={'phase':'Corrected extraction replay; does not replace first_pass or partial corrected_live','rows':[]}
for p in storage.get_batch(db,'rz70')['products']:
 jid=jobs.enqueue(db,p['id'],[1,2,3,4,6]);worker.run_once(db,razer_adapter_factory=lambda:Replay(p['row_number']),dns_adapter_factory=NoDealer);ev=card_evidence.load(db,p['id'],'razer') or {};item={'id':p['row_number'],'input':p,'evidence':ev,'sources':jobs.get_source_pages(db,p['id']),'facts':jobs.get_facts(db,p['id']),'resolved':jobs.get_resolved(db,p['id']),'photos':jobs.get_photo_candidates(db,p['id']),'documents':jobs.get_documents(db,p['id']),'job':jobs.list_jobs(db,p['id'])[0],'readiness':readiness.card_readiness(db,p['id'])};out['rows'].append(item);print(item['id'],item['job']['status'],item['readiness']['confirmed_specs'],ev.get('manual_status'),flush=True)
(R/'corrected_replay_release.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,default=str),encoding='utf8')
