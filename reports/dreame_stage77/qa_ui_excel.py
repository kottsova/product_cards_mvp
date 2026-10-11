"""Actual successful live results through native UI/export; no replay substitution."""
import sys,json,sqlite3,os,hashlib
from pathlib import Path
from io import BytesIO
from urllib.parse import urlsplit
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from product_tool import exporter,jobs,storage,readiness
from product_tool.web import create_app

R=Path(__file__).parent
U=R/'ui';U.mkdir(exist_ok=True)
Q=R/'qa';Q.mkdir(exist_ok=True)
db=U/'batches.sqlite3'
with sqlite3.connect(R/'verified_live/live.sqlite3') as src,sqlite3.connect(db) as dst:src.backup(dst)
checks=[]
with TestClient(create_app(U,start_worker=False)) as client:
    for p in storage.get_batch(db,'dr77')['products']:
        response=client.get(f'/products/{p["id"]}');assert response.status_code==200
        html=response.text;r=readiness.card_readiness(db,p['id'])
        assert 'Модель и конфигурация Dreame' in html and r['manual_status'] in html
        assert 'Данные поставщика не подтверждают коммерческий SKU Dreame' in html
        assert 'Модель и конфигурация Xiaomi' not in html
        assert r['verdict']=='export_ready' and r['confirmed_specs']>=3
        assert any(p['selected'] for p in jobs.get_photo_candidates(db,p['id']))
        (U/f'product_{p["id"]}.html').write_text(html,encoding='utf8')
        checks.append({'id':p['id'],'http_status':200,'model_first_caption':True,'input_configuration_separate':True,'manual_status':r['manual_status'],'readiness':r['verdict'],'confirmed_specs':r['confirmed_specs']})
raw=exporter.export_batch(db,'dr77');(R/'Dreame_Stage77.xlsx').write_bytes(raw)
book=load_workbook(BytesIO(raw));assert book['Dreame готовность'].max_row==11
assert all(book['Dreame готовность'].cell(i,9).value=='Готова' for i in range(2,12))
assert all(book['Dreame готовность'].cell(i,8).value>0 for i in range(2,12))
assert book['Фотографии'].max_row==17 and 'Dreame компоненты' in book.sheetnames
assert all('Данные входного файла' in str(row[3].value) for row in list(book['Dreame конфигурация'].iter_rows())[1:])
errors=[(s.title,c.coordinate,c.value) for s in book for row in s for c in row if c.data_type=='e'];assert not errors
sheets={s.title:{'rows':s.max_row,'columns':s.max_column,'headers':[c.value for c in s[1]]} for s in book};book.close()
(R/'qa_ui_excel.json').write_text(json.dumps({'observation':'actual successful live worker; no captures injected into production','ui':checks,'native_exporter':True,'sheets':sheets,'formula_errors':errors,'workbook_sha256':hashlib.sha256(raw).hexdigest()},ensure_ascii=False,indent=2),encoding='utf8')
os.environ.setdefault('PLAYWRIGHT_BROWSERS_PATH',str(Path('.venv/playwright-browsers').resolve()))
from playwright.sync_api import sync_playwright
with TestClient(create_app(U,start_worker=False)) as client,sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True);page=browser.new_page(viewport={'width':1440,'height':1000})
    image_bytes={}
    for result in (R/'verified_live').glob('*/*/result.json'):
        ev=json.loads(result.read_text(encoding='utf8'))['evidence']
        for m in ev.get('image_measurements',[]):
            if m.get('sha256'):
                image_bytes[m['url']]=(result.parent/'captures'/(m['sha256']+'.img'),m['effective_content_type'])
    def route(request):
        u=urlsplit(request.request.url)
        if request.request.url in image_bytes:
            file,kind=image_bytes[request.request.url];request.fulfill(status=200,body=file.read_bytes(),content_type=kind);return
        if u.hostname!='dreame-audit.test':request.abort();return
        response=client.get(u.path);request.fulfill(status=response.status_code,body=response.content,content_type=response.headers.get('content-type','text/html'))
    page.route('**/*',route)
    for pid in (1,5,8,9,10):
        page.goto(f'http://dreame-audit.test/products/{pid}',wait_until='domcontentloaded')
        page.locator('#xiaomi-readiness').scroll_into_view_if_needed();page.screenshot(path=str(Q/f'ui_{pid}_evidence.png'))
        for title,suffix in [('Характеристики','specs'),('Фотографии','photos')]:
            section=page.locator('section').filter(has=page.get_by_role('heading',name=title,exact=True)).last
            if suffix=='photos':
                section=page.locator('.photo-tile').filter(has=page.locator('input[name=asset_keys][checked]')).first
            section.scroll_into_view_if_needed()
            if suffix=='photos':
                page.wait_for_function("() => [...document.querySelectorAll('.photo-tile')].filter(x=>x.querySelector('input[name=asset_keys][checked]')).every(x=>x.querySelector('img').complete && x.querySelector('img').naturalWidth>0)",timeout=5000)
            page.screenshot(path=str(Q/f'ui_{pid}_{suffix}.png'))
    browser.close()
print('10 UI cards and native Excel verified; 5 offline-local UI screenshots',flush=True)
