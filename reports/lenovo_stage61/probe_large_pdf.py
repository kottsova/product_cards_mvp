from pathlib import Path
import json,re,hashlib,requests
from product_tool.adapters.policy_session import PolicyAwareSession
from product_tool.adapters.lg_documents import BinarySafeSession,document_languages
from product_tool.adapters.lenovo_documents import verify_pdf
from product_tool.adapters.lenovo_psref import read_capture
from pypdf import PdfReader
from io import BytesIO
root=Path('reports/lenovo_stage61');out=root/'psref_captures';reviews=json.loads((out/'manual_reviews.json').read_text(encoding='utf-8'));sources=json.loads((root/'manual_probe.json').read_text(encoding='utf-8'));session=PolicyAwareSession(root/'manual_pdf_fetch_log.json',allowed_hosts=('download.lenovo.com',),underlying=BinarySafeSession(requests.Session()),max_bytes=50000000);results=[]
for source in sources[:2]:
 if not source['url'].endswith('.pdf') or not re.search('_en.pdf|_english_',source['url']):continue
 url=re.sub('_en.pdf','_ru.pdf',source['url']).replace('_english_','_russian_')
 r=session.get(url,timeout=15);item={'source_url':source['url'],'candidate_url':url,'candidate_method':'Observed English filename with standard locale token substitution; URL not evidence','status':r.status_code,'marker':r.marker,'articles':source['articles']}
 if r.ok and not r.truncated:
  raw=r.text.encode('latin-1');name=hashlib.sha256(raw).hexdigest()+'.pdf';(out/name).write_bytes(raw);item['file']=name
  for article in source['articles']:
   capture=read_capture(out,article);family=capture[1]['psref_info']['data']['ProductName'] if capture else article[:4]
   verified=verify_pdf(raw,article,family)
   if verified:
    doc={**verified,'title':'Руководство пользователя (PDF)','format':'pdf','url':url,'source_url':source['url'],'proof_file':name,'proof_sha256':hashlib.sha256(raw).hexdigest()};reviews[article]['documents'].append(doc);reviews[article]['status']='Проверена';item.setdefault('verified_for',[]).append(article)
  if raw.startswith(b'%PDF-'):
   reader=PdfReader(BytesIO(raw));pages=[p.extract_text() or '' for p in reader.pages];item['pages']=len(pages);item['language_assessment']=document_languages(pages);item['cover_text']='\n'.join(pages[:2])[:1800]
 results.append(item);(root/'pdf_language_probe.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8');print(source['articles'],r.status_code,item.get('verified_for',[]),flush=True)
(out/'manual_reviews.json').write_text(json.dumps(reviews,ensure_ascii=False,indent=2),encoding='utf-8')
