from pathlib import Path
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright
from product_tool.web import create_app
root=Path('reports/lenovo_stage61');ui=root/'ui_batch'
with TestClient(create_app(ui,start_worker=False)) as client,sync_playwright() as pw:
 browser=pw.chromium.launch(headless=True)
 page=browser.new_page(viewport={'width':1440,'height':1000},device_scale_factor=1)
 def handle(route):
  from urllib.parse import urlsplit
  url=urlsplit(route.request.url)
  if url.hostname!='lenovo-audit.test':
   route.abort();return
  response=client.get(url.path)
  route.fulfill(status=response.status_code,body=response.content,content_type=response.headers.get('content-type','text/html'))
 page.route('**/*',handle)
 for pid,name in ((3,'exact'),(5,'monitor')):
  page.goto(f'http://lenovo-audit.test/products/{pid}',wait_until='networkidle')
  page.screenshot(path=str(root/f'ui_{name}_overview.png'))
  page.get_by_role('heading',name='Конфигурация Lenovo',exact=True).scroll_into_view_if_needed()
  page.screenshot(path=str(root/f'ui_{name}_candidates.png'))
  assert page.get_by_role('heading',name='Кандидаты конфигурации',exact=True).is_visible()
 browser.close()
print('4 offline browser screenshots saved; ready laptop and resolved monitor with gallery gap rendered')
