"""Actual upload, unedited preview confirmation; baseline isolated from user DB."""
import json,sys,hashlib
sys.stdout.reconfigure(encoding='utf8')
from pathlib import Path
from playwright.sync_api import sync_playwright
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from product_tool import storage
root=Path(__file__).resolve().parents[2];out=Path(__file__).parent;phase=sys.argv[1]
base='http://127.0.0.1:'+('8766' if phase=='before' else '8765');file=out/'Ordinary_3_columns.xlsx';sha=hashlib.sha256(file.read_bytes()).hexdigest()
with sync_playwright() as pw:
 browser=pw.chromium.launch(headless=True);page=browser.new_page(viewport={'width':1900,'height':1100})
 page.goto(base+'/',wait_until='domcontentloaded');form=page.locator('form[action="/upload"]')
 form.locator('input[type=file]').set_input_files(str(file));form.locator('button[type=submit]').click();page.wait_for_url('**/drafts/**')
 draft=page.url.rsplit('/',1)[1];confirm=page.locator(f'form[action="/drafts/{draft}/confirm"]')
 page.screenshot(path=str(out/f'qa/preview_{phase}.png'),full_page=True)
 (out/f'preview_{phase}.html').write_text(page.content(),encoding='utf8')
 proof=dict(phase=phase,draft_id=draft,url=page.url,file_sha256=sha,user_edits=0,model_column=page.get_by_role('columnheader',name='Распознанная модель',exact=True).count(),rows=[])
 for row in range(2,10):
  proof['rows'].append(dict(row=row,brand=confirm.locator(f'[name="brand_{row}"]').input_value(),article=confirm.locator(f'[name="search_code_{row}"]').input_value(),category=confirm.locator(f'[name="category_{row}"]').input_value(),model=confirm.locator(f'[data-model-row="{row}"]').inner_text() if phase!='before' else None,configuration=confirm.locator(f'[data-configuration-row="{row}"]').inner_text() if phase!='before' else None))
 if phase!='before':
  confirm.locator('button[type=submit]').click();page.wait_for_url('**/batches/**')
  proof['batch_url']=page.url
  batch=storage.get_batch(root/'data/batches.sqlite3',draft)
  (out/'batch.json').write_text(json.dumps(batch,ensure_ascii=False,indent=2),encoding='utf8')
  upload=root/'data/uploads'/f'{draft}.xlsx'
  assert hashlib.sha256(upload.read_bytes()).hexdigest()==sha
 browser.close()
assert hashlib.sha256(file.read_bytes()).hexdigest()==sha
(out/f'ui_{phase}.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(proof,ensure_ascii=False),flush=True)
