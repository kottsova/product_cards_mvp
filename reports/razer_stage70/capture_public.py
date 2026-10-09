from pathlib import Path
import json,os,sys,hashlib
from product_tool.census.browser_runtime import discover_runtime,PlaywrightBrowser,BrowserFailure
from product_tool.census.browser_contracts import BrowserBudget
R=Path(__file__).parent
os.environ.setdefault('PLAYWRIGHT_BROWSERS_PATH',str(Path('.venv/playwright-browsers').resolve()))
for url in sys.argv[1:]:
 d=PlaywrightBrowser(discover_runtime(),BrowserBudget(deadline_seconds=25,operation_timeout_seconds=8),('mysupport.razer.com','assets2.razerzone.com','assets.razerzone.com'))
 out={'requested':url}
 try:
  d.start();d.call('goto',url=url,render_mode='render_existing_search_result',search_result_hosts=['mysupport.razer.com']);z=d.call('document_snapshot');html=z.pop('html');key=hashlib.sha256(url.encode()).hexdigest()[:16];file=key+'.html';(R/'observed'/file).write_text(html,encoding='utf8');out.update(z,file=file,sha256=hashlib.sha256(html.encode()).hexdigest())
 except BrowserFailure as e:out.update(error=str(e),counts=e.counts)
 finally:d.close()
 (R/('capture_'+hashlib.sha256(url.encode()).hexdigest()[:16]+'.json')).write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8');print(url,out.get('projection',{}).get('title'),out.get('error'),out.get('file'),flush=True)
