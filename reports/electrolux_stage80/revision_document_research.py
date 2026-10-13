"""Actual candidate PDF fetch, never a replay/confirmed revision substitute."""
import sys,json,re,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import pymupdf
from product_tool.census.public_browser import IsolatedPublicBrowserSession
from product_tool.census.browser_contracts import BrowserBudget
from product_tool.electrolux_page import MEDIA_HOSTS
from product_tool.adapters.electrolux import ElectroluxAdapter
from product_tool.adapters.lg_documents import document_bytes
R=Path(__file__).parent;out=R/'revision_document_research';out.mkdir(exist_ok=True)
ev=json.loads((R/'release_live/10/result.json').read_text(encoding='utf8'))['evidence']
b=IsolatedPublicBrowserSession(allowed_hosts=MEDIA_HOSTS,fetch_log_path=R/'live_fetch_log.json',profile_dir=Path('data/electrolux_stage78_chrome_profile'),visible=True,use_system_ca=True,budget=BrowserBudget(operation_timeout_seconds=10),trace_path=out/'browser_timing.jsonl')
a=ElectroluxAdapter(fetch_log_path=R/'live_fetch_log.json',browser_session=b,capture_dir=out)
results=[]
try:
 b.start()
 for item in ev['document_inventory']:
  if item['type'] not in {'Specification Sheet','Product Fiche','Energy Label','User Manual'}:continue
  result={'origin':'actual live candidate PDF from published live PDP document inventory','type':item['type'],'url':item['url'],'published_product_code':item['product_code'],'requested_pnc':'94949957800','confirmed_revision_relation':False}
  try:
   response=a.binary.get(item['url'],timeout=8);raw=document_bytes(response)
   if not response.ok or response.marker or response.truncated or not raw.startswith(b'%PDF-'):raise ValueError('Candidate PDF transport/type not verified')
   sha=hashlib.sha256(raw).hexdigest();(out/(sha+'.pdf')).write_bytes(raw)
   with pymupdf.open(stream=raw,filetype='pdf') as pdf:
    if len(pdf)>600:raise ValueError('PDF page budget')
    text='\n'.join(p.get_text() for p in pdf)
    result['pages']=len(pdf)
   if len(text)>2000000:raise ValueError('PDF text budget')
   context=[text[max(0,m.start()-110):m.end()+110] for m in re.finditer(r'949\s*499\s*578(?:\s*00|\s*01)?',text)]
   result.update(status_code=response.status_code,sha256=sha,bytes=len(raw),pnc_contexts=context,
                 exact_requested_pnc_mentions=bool(re.search(r'949\s*499\s*578\s*00\b',text)),
                 model_mentioned='EOD6C46K2' in text,file=sha+'.pdf')
   (out/(sha+'.txt')).write_text(text,encoding='utf8',newline='\n')
  except Exception as exc:result['error']=str(exc)
  results.append(result)
finally:b.close()
(R/'revision_document_research.json').write_text(json.dumps({'results':results,'context_closed':b.context is None,'qualification':'candidate research only; no official facts promoted'},ensure_ascii=False,indent=2),encoding='utf8',newline='\n')
print([{'type':x['type'],'exact_requested_pnc_mentions':x.get('exact_requested_pnc_mentions'),'error':x.get('error'),'pnc_contexts':x.get('pnc_contexts',[])} for x in results])
