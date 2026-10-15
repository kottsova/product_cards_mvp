"""Read-only browser assertions against the actual listening application."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
out=Path(__file__).parent
with sync_playwright() as pw:
 browser=pw.chromium.launch(headless=True,channel='chrome');page=browser.new_page(viewport={'width':1440,'height':1000})
 page.goto('http://127.0.0.1:8765/products/92',wait_until='domcontentloaded')
 expected={'Мощность беспроводной зарядки MagSafe, Вт':'До 25 Вт','Мощность беспроводной зарядки Qi2, Вт':'До 25 Вт','Идентификация аксессуаров NFC':'Да','Магнитометр':'Да','Время быстрой зарядки USB-C, мин':'Около 15 мин','Время быстрой зарядки MagSafe, мин':'30 мин'}
 for label,value in expected.items():
  row=page.locator('.card-attributes tbody tr').filter(has=page.get_by_role('rowheader',name=label,exact=True))
  assert row.count()==1,(label,row.count())
  assert row.get_by_role('cell',name=value,exact=True).count()==1,(label,row.inner_text())
 wireless=page.locator('.attribute-group[data-section="Беспроводная зарядка"]').first
 wireless.screenshot(path=str(out/'qa/ui_wireless.png'))
 fast=page.locator('.attribute-group[data-section="Быстрая зарядка"]').first
 fast.screenshot(path=str(out/'qa/ui_fast_charge.png'))
 compatibility=page.locator('.attribute-group[data-section="Совместимость и системные требования"]').first
 assert 'Системные требования' in compatibility.inner_text()
 compatibility.screenshot(path=str(out/'qa/ui_compatibility.png'))
 gallery=page.locator('#photos');img=gallery.locator('img').first
 img.scroll_into_view_if_needed();page.wait_for_function('(img)=>img.complete && img.naturalWidth>0',arg=img.element_handle(),timeout=20000)
 gallery.screenshot(path=str(out/'qa/ui_apple_gallery.png'))
 page.goto('http://127.0.0.1:8765/products/101',wait_until='domcontentloaded')
 assert 'S3WER.ALWPCOM' in page.inner_text('body')
 assert 'export_ready' in page.inner_text('body')
 page.screenshot(path=str(out/'qa/ui_lg_recovered.png'))
 browser.close()
result=dict(apple_product=92,separate_visible_values=expected,compatibility_group=True,actual_gallery_image_loaded=True,original_lg_product=101,lg_export_ready=True)
(out/'ui_qa.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(result,ensure_ascii=False))
