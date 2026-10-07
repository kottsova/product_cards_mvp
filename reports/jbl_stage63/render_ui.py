from pathlib import Path
import json
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright
from product_tool.web import create_app
from urllib.parse import urlsplit,unquote
r=Path('reports/jbl_stage63');mapping={unquote(x['url']):r/x['file'] for x in json.loads((r/'photo_inspection.json').read_text())}
with TestClient(create_app(r/'ui_batch',start_worker=False)) as client,sync_playwright() as pw:
 browser=pw.chromium.launch(headless=True);page=browser.new_page(viewport={'width':1440,'height':1000})
 def handle(route):
  url=urlsplit(route.request.url)
  if unquote(route.request.url) in mapping:route.fulfill(status=200,body=mapping[unquote(route.request.url)].read_bytes(),content_type='image/png');return
  if url.hostname!='jbl-audit.test':route.abort();return
  response=client.get(url.path);route.fulfill(status=response.status_code,body=response.content,content_type=response.headers.get('content-type','text/html'))
 page.route('**/*',handle)
 for pid,name in ((7,'tune_black'),(11,'tune_white'),(4,'xtreme_blue'),(8,'bar500')):
  page.goto(f'http://jbl-audit.test/products/{pid}',wait_until='networkidle');page.screenshot(path=str(r/f'ui_{name}_overview.png'))
  page.get_by_role('heading',name='Проверка JBL',exact=True).scroll_into_view_if_needed();page.screenshot(path=str(r/f'ui_{name}_audit.png'))
  if pid in {7,11,4,8}:
   page.locator('.photo-open').first.click();assert page.locator('#photo-lightbox').is_visible();assert '1605' in page.locator('.lightbox-metadata').inner_text();page.screenshot(path=str(r/f'ui_{name}_lightbox.png'));page.get_by_role('button',name='Закрыть',exact=True).click()
 browser.close()
print('12 recovery UI renders and measured variant lightboxes verified')
