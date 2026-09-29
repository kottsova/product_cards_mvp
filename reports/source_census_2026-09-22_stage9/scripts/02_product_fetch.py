import sys, json, re
sys.path.insert(0, r'C:\Users\Julynce\AppData\Local\Temp\claude\a--work-dev-product-cards-mvp\9962257a-7031-4112-8b5f-503975d81cc3\scratchpad\stage9')
from lib import fetch, save_fixture, save_link_index, OUT, budget_status
from product_tool.census.discovery import json_ld_products, detect_embedded_state
from bs4 import BeautifulSoup

hosts = ('direct.playstation.com',)
url = 'https://direct.playstation.com/en-us/buy-accessories/dualsense-wireless-controller-cosmic-red-for-ps5-pc-mac-mobile'
page, err = fetch(url, hosts, 'product',
                   identity_terms=['DualSense', 'Cosmic Red', 'PS5', 'CFI-ZCT1J', 'CFI-ZCT1W', 'Sony'],
                   reason='re-fetch of the already-verified Stage 8.2 product page to extract REAL microdata field values (sku, name) -- Stage 8.2 only confirmed the microdata FIELD NAMES existed, never the values, by design of the sanitized structural census')
result = {'url': url, 'error': err}
if page:
    text = page['raw_text']
    soup = BeautifulSoup(text, 'html.parser')
    fx = save_fixture(page['struct'])
    li = save_link_index(page['struct'], 'dualsense_product_refetch')
    result['fixture'] = fx
    result['is_product_page'] = page['struct']['is_product_page']
    result['identity_term_matches'] = page['identity_term_matches']

    # Microdata extraction: itemscope/itemtype Product, itemprop sku/name/color/image
    micro = {}
    for node in soup.select('[itemscope][itemtype*="schema.org/Product"], [itemscope][itemtype*="schema.org/product"]'):
        for prop_node in node.select('[itemprop]'):
            prop = prop_node.get('itemprop')
            val = prop_node.get('content') or prop_node.get_text(' ', strip=True)
            micro.setdefault(prop, []).append(val)
    result['microdata_extracted'] = micro

    # Also broaden: any itemprop=sku/name/color/model anywhere on page, not just inside a Product itemscope,
    # in case the Product itemscope wraps a larger region than detected above.
    micro_any = {}
    for prop in ['sku', 'name', 'color', 'model', 'mpn', 'gtin', 'gtin13', 'gtin12', 'brand', 'image']:
        nodes = soup.select(f'[itemprop="{prop}"]')
        vals = [n.get('content') or n.get_text(' ', strip=True) for n in nodes]
        if vals:
            micro_any[prop] = vals
    result['microdata_any_scope'] = micro_any

    result['json_ld'] = list(json_ld_products(text))
    embedded = detect_embedded_state(text)
    result['embedded_state_evidence'] = [{'kind': e.kind, 'script_id': e.script_id, 'keys': list(e.keys)} for e in embedded]

    result['title_tag'] = soup.title.get_text(strip=True) if soup.title else None
    canonical = soup.select_one('link[rel=canonical]')
    result['canonical_url'] = canonical.get('href') if canonical else None

    pdf_links = []
    for a in soup.select('a[href]'):
        href = a.get('href', '')
        if re.search(r'\.pdf(?:[?#]|$)', href, re.I):
            pdf_links.append({'href': href, 'text': a.get_text(' ', strip=True)})
    result['pdf_links_found'] = pdf_links

    img_candidates = []
    for tag in soup.select('img[srcset], source[srcset], img[src]'):
        img_candidates.append({'srcset': tag.get('srcset'), 'src': tag.get('src'), 'alt': tag.get('alt')})
    result['img_candidates'] = img_candidates[:20]

    body_text = soup.get_text('\n', strip=True)
    color_hits = [m.group(0).replace('\n', ' | ') for m in re.finditer(r'.{0,25}(cosmic red|color)\w*.{0,40}', body_text, re.I)][:15]
    result['color_context_snippets'] = color_hits
    code_hits = [m.group(0) for m in re.finditer(r'CFI-[A-Z0-9]+', body_text)][:15]
    result['code_context_hits'] = list(dict.fromkeys(code_hits))
    spec_hits = [m.group(0).replace('\n', ' | ') for m in re.finditer(r'.{0,30}(bluetooth|battery|weight|dimension|haptic|trigger|usb|wireless|charging)\w*.{0,40}', body_text, re.I)][:25]
    result['spec_context_snippets'] = list(dict.fromkeys(spec_hits))

    print('is_product_page', page['struct']['is_product_page'])
    print('title:', result['title_tag'])
    print('canonical:', result['canonical_url'])
    print('microdata_extracted:', json.dumps(micro, ensure_ascii=False))
    print('microdata_any_scope:', json.dumps(micro_any, ensure_ascii=False))
    print('code_context_hits:', result['code_context_hits'])
    print('pdf_links:', pdf_links)
    print('color_context_snippets:', color_hits[:8])
    print('spec_context_snippets:', result['spec_context_snippets'][:15])
else:
    print('FAILED', err)

json.dump(result, open(OUT / 'product_fetch.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
print('budget after:', budget_status())
