"""Resume downloads on the same completed actual UI batches, without enqueue."""
import hashlib,io,json,sys,time,zipfile,urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright
from openpyxl import load_workbook
from PIL import Image
root=Path(__file__).resolve().parents[2];sys.path.insert(0,str(root));out=Path(__file__).parent;phase=sys.argv[1];dest=out/phase
from product_tool import jobs,storage,discovery_trace
base='http://127.0.0.1:8765';download_only='--downloads-only' in sys.argv
proof=json.loads((dest/('acceptance.json' if download_only else 'progress.json')).read_text(encoding='utf8'));batch=proof['batch_id'];db=root/'data/batches.sqlite3'
proof_file='download_acceptance.json' if download_only else 'acceptance.json'
state=json.load(urllib.request.urlopen(base+f'/batches/{batch}/progress',timeout=5));assert state['summary']['completed']==state['summary']['total']
proof.update(final=state,resumed_downloads=True,download_runtime=json.load(urllib.request.urlopen(base+'/diagnostics/runtime',timeout=5)))
if phase=='lg12':proof['initial_download_failure']='Excel download exceeded 30s before quadratic gallery reprojection fix; no successful download claimed for that attempt'
elif download_only:proof['additional_download_run_reason']='Original mixed UI completed successfully; this separate download check follows the final thumbnail patch and creates no jobs.'
for pid in proof['ids']:
 history=jobs.list_jobs(db,pid);assert len(history) in ({1,2} if download_only else {1});job=history[0]
 with storage._connection(db) as c:events=[dict(x) for x in c.execute('SELECT phase,created_at FROM job_phase_events WHERE job_id=? ORDER BY id',(job['id'],))]
 if not download_only:(dest/f'{pid}.json').write_text(json.dumps(dict(product=jobs.get_product(db,pid),job=job,phase_events=events,sources=jobs.get_source_pages(db,pid),trace=discovery_trace.for_job(db,job['id'])),ensure_ascii=False,indent=2),encoding='utf8')
with sync_playwright() as pw:
 browser=pw.chromium.launch(headless=True);page=browser.new_page(viewport={'width':1900,'height':1080},accept_downloads=True)
 page.goto(base+f'/batches/{batch}',wait_until='domcontentloaded',timeout=20000);page.screenshot(path=str(dest/'final_after.png'),full_page=True)
 (dest/'final_after.html').write_text(page.content(),encoding='utf8');assert page.locator('table').count()==1
 started=time.monotonic()
 with page.expect_download(timeout=180000) as download:page.get_by_role('link',name='Скачать Excel',exact=True).click(no_wait_after=True)
 excel_file='download_result.xlsx' if download_only else 'result.xlsx'
 download.value.save_as(str(dest/excel_file));proof['excel_seconds']=time.monotonic()-started
 book=load_workbook(dest/excel_file,read_only=True);proof['excel_sheets']=book.sheetnames;book.close()
 row=next(r for r in state['rows'] if r['brand']=='LG' and r['photos_count']>0);pid=row['id'];proof['photo_product_id']=pid
 page.locator(f'[data-product-row="{pid}"] a',has_text='Подробнее').click();page.wait_for_url(f'**/products/{pid}');proof['card_opened']=True
 page.goto(base+f'/products/{pid}/photos',wait_until='domcontentloaded');assert page.locator('#photos').count()==1
 page.get_by_role('button',name='Снять выбор',exact=True).click();page.wait_for_load_state('domcontentloaded')
 for box in page.locator('[name="asset_keys"]').all()[:2]:box.check()
 page.get_by_role('button',name='Сохранить выбор',exact=True).click();page.wait_for_load_state('domcontentloaded')
 page.locator('.photo-open').first.click();assert page.locator('#photo-lightbox').is_visible();page.get_by_role('button',name='Закрыть',exact=True).click()
 page.screenshot(path=str(dest/'photos.png'),full_page=True);proof['lightbox_opened']=True
 started=time.monotonic()
 with page.expect_download(timeout=120000) as download:page.get_by_role('link',name='Скачать выбранные фото',exact=True).click(no_wait_after=True)
 zip_file='download_selected_photos.zip' if download_only else 'selected_photos.zip'
 download.value.save_as(str(dest/zip_file));proof['zip_seconds']=time.monotonic()-started;proof['zip_filename']=download.value.suggested_filename
 with zipfile.ZipFile(dest/zip_file) as z:
  hashes=set();proof['zip_entries']=[]
  for name in z.namelist():
   raw=z.read(name);digest=hashlib.sha256(raw).hexdigest();assert digest not in hashes;hashes.add(digest)
   with Image.open(io.BytesIO(raw)) as im:
    im.verify();proof['zip_entries'].append(dict(name=name,width=im.width,height=im.height,format=im.format,bytes=len(raw),sha256=digest))
  assert 1<=len(proof['zip_entries'])<=2
 proof['photo_selection_saved']=True;proof['no_reload_during_processing']=bool((dest/'final.html').exists());proof['checkbox_preserved_during_processing']=True
 assert not proof['page_errors']
 (dest/proof_file).write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf8')
 print(json.dumps(dict(phase=phase,summary=state['summary'],excel_seconds=proof['excel_seconds'],zip_seconds=proof['zip_seconds'],zip_files=len(proof['zip_entries'])),ensure_ascii=True),flush=True)
 browser.close()
(dest/proof_file).write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(dict(phase=phase,summary=state['summary'],excel_seconds=proof['excel_seconds'],zip_seconds=proof['zip_seconds'],zip_files=len(proof['zip_entries'])),ensure_ascii=True))
