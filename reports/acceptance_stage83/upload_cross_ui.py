import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from playwright.sync_api import sync_playwright
from product_tool import storage
root=Path(__file__).resolve().parents[2];out=Path(__file__).parent
phase=sys.argv[1] if len(sys.argv)>1 else 'initial'
with sync_playwright() as pw:
 browser=pw.chromium.launch(headless=True,channel='chrome');page=browser.new_page(viewport={'width':1440,'height':1000})
 page.goto('http://127.0.0.1:8765/',wait_until='domcontentloaded')
 form=page.locator('form[action="/upload"]');form.locator('input[type="file"]').set_input_files(str(out/'CrossBrand_Input.xlsx'))
 form.locator('button[type="submit"]').click();page.wait_for_url('**/drafts/**')
 draft=page.url.rsplit('/',1)[1]
 page.locator(f'form[action="/drafts/{draft}/confirm"]').locator('button[type="submit"]').click()
 page.wait_for_url('**/batches/**');page.screenshot(path=str(out/f'qa/cross_batch_import_{phase}.png'),full_page=True)
 browser.close()
batch=storage.get_batch(root/'data/batches.sqlite3',draft)
(out/f'cross_batch_{phase}.json').write_text(json.dumps(batch,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(dict(batch_id=draft,products=[dict(id=p['id'],brand=p['brand'],name=p['name'],effective_article=p['search_code'],input_resolution=p.get('input_resolution')) for p in batch['products']]),ensure_ascii=False),flush=True)
