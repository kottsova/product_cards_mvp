"""Read-only native UI proof after the actual worker run."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
out=Path(__file__).parent
with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,channel='chrome')
    page=browser.new_page(viewport={'width':1440,'height':1000})
    page.goto('http://127.0.0.1:8765/products/84',wait_until='domcontentloaded')
    assert page.get_by_role('heading',name='Модель и конфигурация Apple',exact=True).count()==1
    gallery=page.locator('section').filter(has=page.get_by_role('heading',name='Фотографии',exact=True)).first
    assert gallery.get_by_text('Проверка байтов: Проверены',exact=False).count()==1
    gallery.scroll_into_view_if_needed()
    image=gallery.locator('img').first
    image.scroll_into_view_if_needed()
    page.wait_for_function('(img)=>img.complete && img.naturalWidth>0',arg=image.element_handle(),timeout=20000)
    gallery.screenshot(path=str(out/'ui_gallery.png'))
    model=page.locator('section').filter(has=page.get_by_role('heading',name='Модель и конфигурация Apple',exact=True)).first
    assert 'Готова' in model.inner_text()
    model.screenshot(path=str(out/'ui_model.png'))
    proof=dict(url=page.url,model_ready=True,byte_verified_label=True,image_loaded=True,title=page.title(),browser='installed Chrome; isolated read-only QA context')
    (out/'ui_checks.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(proof,ensure_ascii=False))
    browser.close()
