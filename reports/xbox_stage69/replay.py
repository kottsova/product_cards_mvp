"""Transport-only captured replay. Discovery sees published pages, not a PDP registry."""
import hashlib,json,re,time,sys
from pathlib import Path
from urllib.parse import urlsplit,urlunsplit,quote
from product_tool.adapters.policy_session import PolicyResponse
from product_tool.adapters.xbox import XboxAdapter,_CACHE
from product_tool import jobs,storage,worker,card_evidence,readiness,discovery_trace

R=Path(__file__).parent

def key(url):
 p=urlsplit(url);return urlunsplit((p.scheme,p.netloc,quote(p.path,safe='/+%'),p.query,''))

class CapturedSession:
 def __init__(self):
  self.pages={};self.calls=[];self.headers={}
  for log,directory in ((R/'live_final_e'/'xbox_fetch.json',R/'live_final_e'/'xbox_captures'),):
   for e in json.loads(log.read_text(encoding='utf8')):
    if e.get('status_code')!=200:continue
    final=e.get('final_url') or e['url'];digest=hashlib.sha256(final.encode()).hexdigest()[:20]
    file=next((directory/(digest+s) for s in ('.bin','.pdf','.html') if (directory/(digest+s)).exists()),None)
    if not file:continue
    raw=file.read_bytes();binary=file.suffix in {'.bin','.pdf'}
    text=raw.decode('latin1') if binary else raw.decode('utf8')
    # Old gzip captures whose bytes were destroyed by UTF8 decoding cannot replay.
    if final.endswith('.gz') and not raw.startswith(b'\x1f\x8b') and not text.lstrip('\ufeff \r\n').startswith('<'):continue
    item=dict(file=str(file),sha256=hashlib.sha256(raw).hexdigest(),text=text,url=final,date=e.get('checked_at'),binary=binary)
    for url in (e['url'],final):self.pages[key(url)]=item
 def get(self,url,**kwargs):
  item=self.pages.get(key(url));self.calls.append(dict(url=url,found=bool(item),file=item['file'] if item else '',sha256=item['sha256'] if item else ''))
  if not item:return PolicyResponse(url,404,'Captured response unavailable')
  return PolicyResponse(item['url'],200,item['text'],'application/pdf' if item['binary'] else 'text/html')

class NoSearch:
 def search_provider(self,provider,query):
  class Result:candidates=[];outcome='captured_search_no_verified_candidates'
  return Result()
 def close(self):pass

if __name__=='__main__':
 sha=hashlib.sha256((R.parent/'xbox_stage68'/'dataset.json').read_bytes()).hexdigest();assert sha==(R.parent/'xbox_stage68'/'dataset.sha256').read_text().strip()
 phase=sys.argv[1] if len(sys.argv)>1 else 'acceptance_replay';db=R/(phase+'.sqlite3');assert not db.exists(),'Never overwrite acceptance database'
 rows=json.loads((R.parent/'xbox_stage68'/'dataset.json').read_text(encoding='utf8'))['rows'];jobs.initialize(db);discovery_trace.initialize(db)
 with storage._connection(db) as c:
  c.execute('INSERT INTO batches VALUES (?,?,?,?,?)',('xb69','Xbox Stage 69','Products','{}',storage._now()))
  for row in rows:c.execute('INSERT INTO products (batch_id,row_number,name,brand,search_code,alternate_code,category,needs_confirmation,issues_json,original_values_json) VALUES (?,?,?,?,?,?,?,?,?,?)',('xb69',row['row'],row['name'],row['brand'],row['article'],'',row['category'],0,'[]',json.dumps({'requested_region':row['requested_region'],'identifier_type':row['identifier_type']})))
 transport=CapturedSession();out=dict(stage=69,dataset_sha256=sha,transport='Captured public HTTP responses; no network; not a live discovery success claim',rows=[],source_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in Path('product_tool').rglob('*.py')})
 for p in storage.get_batch(db,'xb69')['products']:
  jid=jobs.enqueue(db,p['id'],[1,2,3,4,6]);a=XboxAdapter(fetch_log_path=R/'replay_http.json',session=transport,search_factory=NoSearch,trace_callback=lambda e:discovery_trace.record(db,jid,p['id'],e))
  worker.run_once(db,xbox_adapter_factory=lambda:a)
  result=dict(input=p,job=jobs.list_jobs(db,p['id'])[0],readiness=readiness.card_readiness(db,p['id']),evidence=card_evidence.load(db,p['id'],'xbox') or {},sources=jobs.get_source_pages(db,p['id']),facts=jobs.get_facts(db,p['id']),resolved=jobs.get_resolved(db,p['id']),photos=jobs.get_photo_candidates(db,p['id']),trace=discovery_trace.for_job(db,jid))
  out['rows'].append(result);print(p['row_number'],p['search_code'],result['job']['status'],result['readiness']['verdict'],len(result['facts']),len(result['photos']),result['readiness']['blocking_gaps'],flush=True)
 out['calls']=transport.calls;assert sha==hashlib.sha256((R.parent/'xbox_stage68'/'dataset.json').read_bytes()).hexdigest();(R/(phase+'.json')).write_text(json.dumps(out,ensure_ascii=False,indent=2,default=str),encoding='utf8')
