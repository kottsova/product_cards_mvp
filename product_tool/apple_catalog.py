"""Public official catalog identity, without treating a price list as specifications."""
import re
from .adapters.common import clean_text

URL='https://www.apple.com/education/purchase/contracts/docs/NASPO_PSS_Apple_Branded.pdf'

def catalog_descriptions(text,sku):
 descriptions=set()
 for line in text.splitlines():
  m=re.search(r'(?<![A-Z0-9])'+re.escape(sku)+r'\s+(.+?)\s+\$?\d[\d,]*\.\d{2}(?:\s|$)',line,re.I)
  if m:descriptions.add(clean_text(m[1]))
 return descriptions

def lookup(adapter,sku,deadline):
 from .adapters.policy_session import PolicyAwareSession
 from .adapters.lg_documents import BinarySafeSession
 from .adapters.common import SourceDocument
 from .apple_identity import identify
 from pypdf import PdfReader
 from pypdf.errors import PdfReadError
 from io import BytesIO
 import requests,hashlib,json
 session=PolicyAwareSession(adapter.log.with_name('apple_catalog_http.json'),allowed_hosts=('apple.com',),underlying=BinarySafeSession(requests.Session()),max_bytes=8_000_000)
 if adapter.clock()>=deadline:return None
 z=session.get(URL,timeout=min(10,max(.1,deadline-adapter.clock())))
 if not z.ok or z.truncated:return None
 data=z.text.encode('latin-1');sha=hashlib.sha256(data).hexdigest();(adapter.capture_dir/(sha+'.pdf')).write_bytes(data)
 found=set();proof=[]
 try:
  for i,page in enumerate(PdfReader(BytesIO(data)).pages):
   if adapter.clock()>=deadline:return None
   text=page.extract_text(extraction_mode='layout') or '';descriptions=catalog_descriptions(text,sku)
   if descriptions:found.update(descriptions);proof.append({'page':i+1,'description':sorted(descriptions)})
 except (ValueError,TypeError,PdfReadError):return None
 accepted=len(found)==1 and bool(identify(next(iter(found))))
 adapter.emit(event='apple_catalog_identity',query=sku,provider='official_public_catalog',url=z.url,region='us',source_type='commercial_catalog_pdf',accepted=accepted,reason='Unique exact part-number row; model identity only' if accepted else 'Missing/ambiguous SKU model relation',identity_relation='exact_part_number_to_model' if accepted else 'unproven')
 if not accepted:return None
 title=next(iter(found));ev={'identity':{'model':'catalog_model','configuration':'exact_part_number','variant':'unproven','part_number':sku,'hardware_model_numbers':[]},'raw_specs':[],'configuration_candidates':[],'photo_candidates':[],'manual_status':'Не проверена','manuals':[],'catalog_identity':{'url':z.url,'sha256':sha,'rows':proof}}
 (adapter.capture_dir/(sha+'.json')).write_text(json.dumps(ev['catalog_identity']),encoding='utf-8')
 return SourceDocument('apple','Apple official catalog',z.url,found_model=title,match_level='full_sku',evidence='Public official catalog exact SKU row establishes model; not a PDP or configuration spec source'),ev
