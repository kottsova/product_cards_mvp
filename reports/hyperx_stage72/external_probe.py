"""Existing bounded browser fallback after the frozen RU official exact miss."""
import sys,json,os
from pathlib import Path
from dataclasses import asdict
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from product_tool.adapters.lg_browser_search import LGBrowserSearch
from product_tool.census.browser_contracts import BrowserBudget
R=Path(__file__).parent
os.environ.setdefault('PLAYWRIGHT_BROWSERS_PATH',str(Path('.venv/playwright-browsers').resolve()))
rows=json.loads((R/'live_final.json').read_text(encoding='utf8'))['rows']
assert rows[9]['evidence']['configuration_relation']=='unverified'
s=LGBrowserSearch(R/'external_fetch_log.json',official_host='hyperx.com',official_hosts=('hyperx.com','row.hyperx.com','uk.hyperx.com','supportcenter.hyperx.com'),allowed_hosts=('hyperx.com','google.com','gstatic.com','bing.com','duckduckgo.com'),budget=BrowserBudget(deadline_seconds=15,operation_timeout_seconds=5))
events=[];s.trace_callback=events.append
try:
 result=s.search_provider('google','site:hyperx.com "4P5D6AX#ACB"')
 out={'origin':'actual live common browser fallback after official exact miss','result':asdict(result),'trace':events,'no_captcha_bypass':True}
except Exception as e:out={'origin':'actual live common browser fallback attempt','error':str(e),'type':type(e).__name__,'trace':events,'no_captcha_bypass':True}
finally:s.close()
(R/'external_probe.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,default=str),encoding='utf8')
print(out.get('result',{}).get('outcome') or out.get('error'),flush=True)
