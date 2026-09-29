"""Use the single reserved document GET on the first KZ-linked blender manual."""
from __future__ import annotations
import hashlib, io, json, logging, sys
from pathlib import Path
import requests
from pypdf import PdfReader

HERE=Path(__file__).resolve().parent
STAGE=HERE.parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT))
logging.disable(logging.CRITICAL)
from product_tool.adapters.common import SourceError,fetch_with_retry
from product_tool.adapters.lg_documents import BinarySafeSession,assess_document,document_bytes,looks_like_pdf
from product_tool.adapters.policy_fetch import stopped_hosts_from_fetch_log
from product_tool.adapters.policy_session import PolicyAwareSession,RequestBudget,record_responses,request_budget

def main():
    declaration=json.loads((STAGE/'raw/declaration.json').read_text(encoding='utf-8'))
    pages=json.loads((STAGE/'raw/limited_pages_result.json').read_text(encoding='utf-8'))
    assert pages['budget_spent']==3 and not pages['stopped_hosts']
    extracted=json.loads((STAGE/'raw/kz_page_extract.json').read_text(encoding='utf-8'))
    records=extracted['MMB2111M']['document_occurrences']
    url='https://media3.bsh-group.com/Documents/8001232848_B.pdf'
    assert any(x['url']==url and '"titleKey":"user-manuals"' in x['context'] for x in records)
    assert not (STAGE/'document_check').exists(), 'Never repeat this document probe'
    log=STAGE/'document_check/workdir/bosch_fetch_log.json'
    plain=requests.Session()
    plain.headers.update({'User-Agent':'ProductCardsSourceCensus/2.0 (bounded diagnostic probe)'})
    client=PolicyAwareSession(log,allowed_hosts=('media3.bsh-group.com',),underlying=BinarySafeSession(plain),
        max_bytes=declaration['budget']['document_cap_bytes'],min_interval_seconds=declaration['budget']['pacing_seconds'])
    budget=RequestBudget(max_per_row=1,max_total=1)
    budget.begin_row('MMB2111M_manual')
    result={'url':url,'observed_on':extracted['MMB2111M']['url']}
    try:
        with record_responses(STAGE/'document_check/responses'),request_budget(budget):
            response=fetch_with_retry(client,url,deadline=1e12,clock=lambda:0.0)
        body=document_bytes(response)
        result.update({'status':response.status_code,'final_url':response.url,'bytes':len(body),
                       'sha256':hashlib.sha256(body).hexdigest(),'is_pdf':looks_like_pdf(body),
                       'truncated':response.truncated})
        if looks_like_pdf(body) and not response.truncated:
            reader=PdfReader(io.BytesIO(body))
            text=[page.extract_text() or '' for page in reader.pages]
            result['pages']=len(text)
            result['assessment']=assess_document(text,['MMB2111M'])
            result['first_page_excerpt']=text[0][:400]
            import gzip
            with gzip.open(STAGE/'raw/MMB2111M_manual_text.txt.gz','wt',encoding='utf-8') as stream:
                stream.write('\n\f\n'.join(text))
    except SourceError as exc:
        result['error']=str(exc)[:500]
    result['budget_spent_this_step']=budget.total
    result['budget_spent_cumulative']=3+budget.total
    result['stopped_hosts']=sorted(stopped_hosts_from_fetch_log(x for x in json.loads(log.read_text(encoding='utf-8')) if isinstance(x,dict))) if log.exists() else []
    (STAGE/'raw/MMB2111M_manual_result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=True,indent=2))
if __name__=='__main__':main()
