"""One ordinary visible persistent visit, no challenge interaction or retry."""
import json,sys,time
from dataclasses import asdict
from pathlib import Path
from bs4 import BeautifulSoup
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from product_tool.census.public_browser import PublicBrowserSession
from product_tool.census.browser_contracts import BrowserBudget
from product_tool.adapters import policy_fetch, access_stop
from product_tool.adapters.sulpak import SulpakAdapter,KNOWN_LG_URLS
root=Path(__file__).resolve().parents[2];out=Path(__file__).parent
recovered='--recovered' in sys.argv
prefix='sulpak_recovered' if recovered else 'sulpak'
url=KNOWN_LG_URLS['P12ED.NSAR + P12ED.USAR'];log=root/'data/lg_fetch_log.json'
result={'url':url,'flow':'actual visible persistent Chrome, one bounded navigation','stops_before':access_stop.active_stops(policy_fetch.read_log(log))}
session=PublicBrowserSession(allowed_hosts=('sulpak.kz',),fetch_log_path=log,profile_dir=root/'data/sulpak_browser_profile',visible=True,budget=BrowserBudget(deadline_seconds=25,operation_timeout_seconds=10,max_dom_bytes=1000000))
try:
 session.start();session.call('goto',url=url);capture=session.snapshot();result.update(capture);html=result.pop('html')
 (out/(prefix+'_actual_dom.html')).write_text(html,encoding='utf8')
 soup=BeautifulSoup(html,'html.parser');doc=SulpakAdapter().parse_page('P12ED.NSAR + P12ED.USAR',capture['url'],html)
 result.update(title=soup.title.get_text(' ',strip=True) if soup.title else '',h1=[x.get_text(' ',strip=True) for x in soup.select('h1')],jsonld=[s.get_text() for s in soup.select('script[type="application/ld+json"]')],canonical=[x.get('href') for x in soup.select('link[rel="canonical"]')],script_count=len(soup.select('script')),identity=doc.match_level,evidence=doc.evidence,facts=[asdict(a) for a in doc.attributes],photos=[asdict(p) for p in doc.photo_candidates])
 if recovered:
  from product_tool import jobs
  db=root/'data/batches.sqlite3'
  before=dict(sources=[s for s in jobs.get_source_pages(db,172) if s['source_key']!='sulpak'],documents=jobs.get_documents(db,172))
  jobs.save_source_document(db,172,doc)
  after=dict(sources=[s for s in jobs.get_source_pages(db,172) if s['source_key']!='sulpak'],documents=jobs.get_documents(db,172))
  assert before==after,'Official/support evidence changed'
  result.update(persisted_product_id=172,official_support_manual_evidence_unchanged=True)
except Exception as exc:
 result.update(error=type(exc).__name__+': '+str(exc),signal=session.signal,counts=session.counts,response_events=session.events)
 if session.page:
  html=session.page.content();(out/(prefix+'_blocked_dom.html')).write_text(html,encoding='utf8');result['title']=BeautifulSoup(html,'html.parser').title.get_text(' ',strip=True) if BeautifulSoup(html,'html.parser').title else ''
finally:
 result['stops_after']=access_stop.active_stops(policy_fetch.read_log(log));(out/(prefix+'_probe.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');session.close()
print(json.dumps({k:v for k,v in result.items() if k not in {'jsonld'}},ensure_ascii=True))
