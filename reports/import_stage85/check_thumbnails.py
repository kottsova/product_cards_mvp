"""Observe real image loads, not just the presence of thumbnail elements."""
import json,sys
from pathlib import Path
from playwright.sync_api import sync_playwright
out=Path(__file__).parent;failures=[]
with sync_playwright() as pw:
 browser=pw.chromium.launch(headless=True);page=browser.new_page(viewport={'width':1600,'height':1000})
 page.on('requestfailed',lambda r:failures.append(dict(url=r.url,error=r.failure)))
 for attempt in range(2):
  try:page.goto('http://127.0.0.1:8765/products/196/photos',wait_until='domcontentloaded',timeout=15000);break
  except Exception:
   if attempt:raise
 try:page.wait_for_function('document.images.length && [...document.images].slice(0,8).every(i=>i.naturalWidth>0)',timeout=45000)
 except Exception:pass
 result=dict(images=page.locator('img').evaluate_all('(images)=>images.slice(0,8).map(i=>({src:i.src,complete:i.complete,width:i.naturalWidth,height:i.naturalHeight}))'),failures=failures)
 page.locator('.photo-open').first.click();page.wait_for_function('document.querySelector(".lightbox-image").naturalWidth>0',timeout=15000)
 result['lightbox_decoded']=True;page.screenshot(path=str(out/'photo_lightbox_after.png'));page.get_by_role('button',name='Закрыть',exact=True).click()
 page.screenshot(path=str(out/'photo_viewport_after.png'));(out/'thumbnail_load_after.json').write_text(json.dumps(result,indent=2),encoding='utf8');print(json.dumps(result),flush=True);browser.close()
