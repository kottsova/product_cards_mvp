"""Offline Chromium fixture validation of the actual worker projection function.

Run with the already installed Playwright interpreter. No external requests.
"""
from pathlib import Path
import json
from playwright.sync_api import sync_playwright

script=Path('product_tool/census/browser_projection.js').read_text(encoding='utf-8-sig')
policy={'allowed_hosts':['example.com'],'queries':['ABC-123'],'max_fragment_bytes':12000,'max_projection_bytes':120000,'max_projection_fragments':100}
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    context=browser.new_context(service_workers='block')
    page=context.new_page()
    fixture='<html><head><title>Fixture</title></head><body><nav><div class="product-card"><a href="/products/NAV">NAV</a></div></nav><form role="search"><label for="session-generated-123">Search</label><input type="search" id="session-generated-123" name="q"></form><div class="product-card"><h3>ABC-123</h3><a href="/products/ABC-123">ABC-123</a></div><script type="application/ld+json">{"@type":"Product","model":"ABC-123","password":"secret"}</script><div itemscope itemtype="https://schema.org/Product"><meta itemprop="model" content="ABC-123"></div><footer><a href="/products/FOOTER">Footer</a></footer><div>'+('unrelated '*150000)+'</div></body></html>'
    context.route('**/*',lambda route:route.fulfill(status=200,content_type='text/html',body=fixture))
    page.goto('https://example.com/search')
    value=page.evaluate(script,policy);wire=json.dumps(value)
    assert not value.get('overflow') and len(wire)<6000
    assert 'unrelated' not in wire and 'NAV' not in wire and 'FOOTER' not in wire
    assert 'session-generated' not in wire and 'secret' not in wire
    assert not page.evaluate(script,dict(policy,render_mode='render_existing_search_result'))['inputs']
    assert len(value['inputs'])==1 and not value['inputs'][0]['unsafe']
    assert {f['type'] for f in value['fragments']}=={'result_link','json_ld','microdata'}
    assert page.evaluate(script,dict(policy,max_projection_bytes=100)).get('overflow')
    assert page.evaluate(script,dict(policy,max_fragment_bytes=10)).get('overflow')
    page.locator('form').evaluate("f=>{let e=document.createElement('input');e.type='hidden';e.name='csrf';e.value='TOPSECRET';f.appendChild(e)}")
    unsafe=page.evaluate(script,policy)
    assert unsafe['inputs'][0]['security_input'] and unsafe['inputs'][0]['unsafe']
    assert 'TOPSECRET' not in json.dumps(unsafe)
    print(json.dumps({'assertions':11,'fixture_bytes':len(fixture.encode()),'projection_bytes':len(wire.encode()),'projection':value}))
    context.close();browser.close()
