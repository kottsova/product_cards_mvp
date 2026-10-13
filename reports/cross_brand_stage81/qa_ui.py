"""Native app interaction QA from actual-live audit DB; browser network is offline."""
import sys,json,os
from pathlib import Path
from urllib.parse import urlsplit
sys.path.insert(0,str(Path(__file__).resolve().parents[2]));sys.stdout.reconfigure(encoding='utf8')
from product_tool.web import create_app
from product_tool import photo_inventory
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright
R=Path(__file__).parent;phase=sys.argv[1] if len(sys.argv)>1 else 'qualified_live'
U=R/(phase+'_audit')/'ui';db=U/'batches.sqlite3';Q=R/'qa'/'final_ui';Q.mkdir(exist_ok=True)
os.environ.setdefault('PLAYWRIGHT_BROWSERS_PATH',str(Path('.venv/playwright-browsers').resolve()))
representatives=(1,7,30,45,52,60,67,75,81,90,97);images={}
for pid in representatives:
 for photo in photo_inventory.enriched_photos(db,pid):
  file=Path(photo.get('saved_file',''))
  if photo.get('byte_verified') and file.is_file():images[photo['url']]=(file,photo.get('effective_content_type','image/jpeg'))
checks=[]
with TestClient(create_app(U,start_worker=False),base_url='http://stage81-audit.test') as client,sync_playwright() as pw:
 browser=pw.chromium.launch(headless=True);page=browser.new_page(viewport={'width':1440,'height':1000})
 def route(request):
  url=request.request.url
  if url in images:
   file,kind=images[url];request.fulfill(status=200,body=file.read_bytes(),content_type=kind);return
  parts=urlsplit(url)
  if parts.hostname!='stage81-audit.test':request.abort();return
  response=client.get(parts.path+('?' +parts.query if parts.query else ''))
  request.fulfill(status=response.status_code,body=response.content,content_type=response.headers.get('content-type','text/html'))
 page.route('**/*',route)
 for pid in representatives:
  page.goto('http://stage81-audit.test/products/'+str(pid),wait_until='domcontentloaded')
  field=page.locator('#attribute-search');field.scroll_into_view_if_needed()
  total=page.locator('.card-attributes tbody > tr').count();assert total>0
  field.fill('stage81_impossible_query');assert page.locator('.attribute-group:visible').count()==0
  field.fill('');assert page.locator('.card-attributes tbody > tr:visible').count()==total
  page.locator('#attribute-role').select_option('feature')
  assert page.locator('.attribute-group[data-role="core"]:visible').count()==0
  page.locator('#attribute-role').select_option('all')
  field.scroll_into_view_if_needed();page.screenshot(path=str(Q/f'attributes_{pid}.png'))
  tiles=page.locator('.photo-tile');photos=tiles.count();opened=False
  if photos:
   first=tiles.first;first.scroll_into_view_if_needed();page.screenshot(path=str(Q/f'gallery_{pid}.png'))
   (Q/f'layout_{pid}.json').write_text(json.dumps(page.evaluate("() => ({styles:[...document.styleSheets].map(s=>s.href),tiles:[...document.querySelectorAll('.photo-tile')].slice(0,2).map(t=>({tile:t.getBoundingClientRect().toJSON(),button:t.querySelector('.photo-open').getBoundingClientRect().toJSON(),image:t.querySelector('img').getBoundingClientRect().toJSON(),grid:getComputedStyle(t).gridTemplateColumns}))})"),indent=2),encoding='utf8')
   first.locator('.photo-open').click();dialog=page.locator('dialog');assert dialog.is_visible();opened=True
   page.screenshot(path=str(Q/f'large_photo_{pid}.png'));page.keyboard.press('Escape')
  checks.append({'id':pid,'attributes':total,'search_and_role_filter':True,'gallery_tiles':photos,'large_photo':opened,'image_display':'Saved byte-verified bytes only; no new external request or replay live claim'})
 browser.close()
(Q/'interaction_checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print('Native interactive UI QA',len(checks),'brands',flush=True)
