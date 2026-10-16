"""Read-only screenshots of the actual release batch and JBL model/color card."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
out=Path(__file__).parent
batch=json.loads((out/'batch.json').read_text(encoding='utf8'))
with sync_playwright() as pw:
 browser=pw.chromium.launch(headless=True)
 page=browser.new_page(viewport={'width':1900,'height':1100})
 observations=[]
 ids={p['brand']:p['id'] for p in batch['products'][:5]}
 for name,url in [('batch',f"/batches/{batch['id']}"),('jbl',f"/products/{ids['JBL']}"),('apple',f"/products/{ids['Apple']}")]:
  response=page.goto('http://127.0.0.1:8765'+url,wait_until='domcontentloaded')
  assert response.status==200
  page.screenshot(path=str(out/f'qa/result_{name}.png'))
  observations.append(dict(page=name,url=page.url,status=response.status,headings=page.locator('h1,h2').all_text_contents(),text=page.locator('body').inner_text()[:4500]))
 browser.close()
(out/'ui_result.json').write_text(json.dumps(observations,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps([dict(page=o['page'],status=o['status']) for o in observations]))
