"""Native UI and Excel read actual live DB; no replay substituted."""
import sys,json,sqlite3,hashlib,os
from pathlib import Path
from io import BytesIO
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from product_tool import jobs,storage,readiness,exporter
from product_tool.web import create_app
R=Path(__file__).parent;L=R/'release_live';assert len(json.loads((L/'summary.json').read_text(encoding='utf8'))['rows'])==10
U=R/'ui';U.mkdir(exist_ok=True);Q=R/'qa';Q.mkdir(exist_ok=True);db=U/'batches.sqlite3'
with sqlite3.connect(L/'live.sqlite3') as src,sqlite3.connect(db) as dst:src.backup(dst)
checks=[]
with TestClient(create_app(U,start_worker=False)) as client:
 for p in storage.get_batch(db,'el80')['products']:
  response=client.get('/products/'+str(p['id']));assert response.status_code==200;html=response.text;r=readiness.card_readiness(db,p['id']);assert 'Модель и PNC Electrolux' in html and r['manual_status'] in html
  assert r['verdict']=='not_ready' or r['confirmed_specs']>=3
  (U/f'product_{p["id"]}.html').write_bytes(html.encode('utf8'));checks.append({'id':p['id'],'http_status':response.status_code,'readiness':r['verdict'],'manual_status':r['manual_status'],'blocking_gaps':r['blocking_gaps']})
raw=exporter.export_batch(db,'el80');(R/'Electrolux_Stage80.xlsx').write_bytes(raw);book=load_workbook(BytesIO(raw));assert book['Electrolux готовность'].max_row==11
assert {'Electrolux исходные','Electrolux документы'}<=set(book.sheetnames)
errors=[(s.title,c.coordinate) for s in book for row in s for c in row if c.data_type=='e'];assert not errors
sheets={s.title:{'rows':s.max_row,'columns':s.max_column,'headers':[c.value for c in s[1]]} for s in book};book.close()
out={'observation':'native UI and native Excel exporter from actual full_live worker DB','ui':checks,'workbook_sha256':hashlib.sha256(raw).hexdigest(),'sheets':sheets,'formula_errors':errors}
os.environ.setdefault('PLAYWRIGHT_BROWSERS_PATH',str(Path('.venv/playwright-browsers').resolve()))
from playwright.sync_api import sync_playwright
images={}
for result in L.glob('*/result.json'):
 ev=json.loads(result.read_text(encoding='utf8'))['evidence']
 for m in ev.get('image_measurements',[]):
  if m.get('sha256'):images[m['url']]=(result.parent/'captures'/(m['sha256']+'.img'),m['effective_content_type'])
with TestClient(create_app(U,start_worker=False)) as client,sync_playwright() as pw:
 browser=pw.chromium.launch(headless=True);page=browser.new_page(viewport={'width':1440,'height':1000})
 def route(route):
  from urllib.parse import urlsplit
  u=route.request.url
  if u in images:
   file,kind=images[u];route.fulfill(status=200,body=file.read_bytes(),content_type=kind);return
  parts=urlsplit(u)
  if parts.hostname!='electrolux-audit.test':route.abort();return
  response=client.get(parts.path);route.fulfill(status=response.status_code,body=response.content,content_type=response.headers.get('content-type','text/html'))
 page.route('**/*',route)
 for pid in (1,3,5,6,8,10):
  page.goto(f'http://electrolux-audit.test/products/{pid}',wait_until='domcontentloaded');page.locator('#electrolux-readiness').scroll_into_view_if_needed();page.screenshot(path=str(Q/f'ui_{pid}_identity.png'))
  section=page.locator('section').filter(has=page.get_by_role('heading',name='Характеристики',exact=True)).last
  if section.count():section.scroll_into_view_if_needed();page.screenshot(path=str(Q/f'ui_{pid}_specs.png'))
 browser.close()
(R/'qa_ui_excel.json').write_bytes((json.dumps(out,ensure_ascii=False,indent=2)+'\n').encode('utf8'));print({'ui_cards':len(checks),'sheets':len(sheets),'formula_errors':len(errors)},flush=True)
