"""One fresh visible persistent session, roots/search only, no replay or retry."""
import json,os,hashlib
from pathlib import Path
from product_tool.census.public_browser import PublicBrowserSession
from product_tool.census.browser_runtime import BrowserFailure
R=Path(__file__).parent;os.environ.setdefault('PLAYWRIGHT_BROWSERS_PATH',str(Path('.venv/playwright-browsers').resolve()))
d=PublicBrowserSession(allowed_hosts=('razer.com','razerzone.com'),fetch_log_path=R/'razer_fetch_log.json',profile_dir=R/'attended_profile',visible=True)
out=[]
try:
 d.start()
 for url in ('https://www.razer.com/','https://mysupport.razer.com/app/answers/list/kw/RZ03-0339','https://mysupport.razer.com/app/answers/list/kw/RZ04-0443'):
  z={'requested':url}
  try:
   d.call('goto',url=url);z.update(d.call('document_snapshot'));html=z.pop('html');file=hashlib.sha256(html.encode()).hexdigest()+'.html';(R/'observed').mkdir(exist_ok=True);(R/'observed'/file).write_text(html,encoding='utf8');z['file']=file
  except BrowserFailure as e:z.update(error=str(e),counts=e.counts)
  out.append(z);(R/'probe.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8');print(url,z.get('status_code'),z.get('error'),z.get('file'),flush=True)
finally:d.close()
