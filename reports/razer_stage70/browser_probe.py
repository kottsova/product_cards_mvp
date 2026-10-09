"""One bounded read-only render via existing browser runtime; challenge stops retained."""
from pathlib import Path
import json,os
from product_tool.census.browser_runtime import discover_runtime,PlaywrightBrowser,BrowserFailure
from product_tool.census.browser_contracts import BrowserBudget
R=Path(__file__).parent;os.environ.setdefault('PLAYWRIGHT_BROWSERS_PATH',str(Path('.venv/playwright-browsers').resolve()))
runtime=discover_runtime();driver=PlaywrightBrowser(runtime,BrowserBudget(deadline_seconds=25,operation_timeout_seconds=8),('mysupport.razer.com','assets2.razerzone.com','assets.razerzone.com'));out=dict(runtime=runtime.to_dict())
try:
 out['start']=driver.start();out['result']=driver.call('goto',url='https://mysupport.razer.com/app/answers/detail/a_id/6124',queries=['RZ01-04640100-R3U1','Razer DeathAdder V3'],render_mode='render_existing_search_result',search_result_hosts=['mysupport.razer.com'])
 snapshot=driver.call('document_snapshot');html=snapshot.pop('html');(R/'observed'/'support_6124.html').write_text(html,encoding='utf8');out['snapshot']=snapshot
except BrowserFailure as e:out.update(outcome=str(e),counts=e.counts)
finally:driver.close()
(R/'browser_probe.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(out,ensure_ascii=False)[:1500])
