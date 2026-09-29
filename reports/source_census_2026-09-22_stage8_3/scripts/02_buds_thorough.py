import sys, json, re
sys.path.insert(0, r'C:\Users\Julynce\AppData\Local\Temp\claude\a--work-dev-product-cards-mvp\9962257a-7031-4112-8b5f-503975d81cc3\scratchpad\stage83')
from lib import fetch, save_fixture, OUT, budget_status
from product_tool.census.discovery import json_ld_products, detect_embedded_state
from bs4 import BeautifulSoup

hosts = ('www.samsung.com',)
url = 'https://www.samsung.com/kz_ru/audio-sound/galaxy-buds/galaxy-buds3-fe-black-sm-r420nzkacis/'
page, err = fetch(url, hosts, 'product', identity_terms=['Galaxy Buds3 FE', 'Черный', 'Black', 'Bluetooth', 'мАч', 'mAh'],
                   reason='second, final targeted pass on the same already-confirmed product page: the first pass captured JSON-LD (name/sku/image) but not color/spec/embedded-state evidence, which requires a full-text/DOM search performed within the same fetch (raw HTML is not persisted between requests, so this could not be done from the first pass after the fact)')
result = {'url': url, 'error': err}
if page:
    text = page['raw_text']
    soup = BeautifulSoup(text, 'html.parser')
    result['json_ld'] = list(json_ld_products(text))
    embedded = detect_embedded_state(text)
    result['embedded_state_evidence'] = [
        {'kind': e.kind, 'script_id': e.script_id, 'keys': list(e.keys)} for e in embedded
    ]
    # search visible text for color / spec hints near the product title area
    body_text = soup.get_text('\n', strip=True)
    color_hits = [m for m in re.finditer(r'.{0,40}(цвет|color)\s*[:\-]?\s*.{0,40}', body_text, re.I)]
    result['color_context_snippets'] = [h.group(0) for h in color_hits[:10]]
    black_hits = [m.group(0) for m in re.finditer(r'.{0,25}(черный|чёрный|black)\b.{0,25}', body_text, re.I)][:10]
    result['black_context_snippets'] = black_hits
    # look for a color swatch / variant selector structure
    swatch_like = soup.select('[class*=color], [class*=swatch], [data-color], [aria-label*=олор i]')
    result['swatch_like_elements'] = [{'tag': t.name, 'class': t.get('class'), 'aria_label': t.get('aria-label'), 'data_color': t.get('data-color')} for t in swatch_like[:15]]
    # bluetooth / battery spec mentions anywhere in text (loose signal only)
    spec_hits = [m.group(0) for m in re.finditer(r'.{0,30}(bluetooth|мач|mah|ip\d{2}|активное шумоподавление|anc)\b.{0,30}', body_text, re.I)][:15]
    result['spec_context_snippets'] = spec_hits
    result['title_tag'] = soup.title.get_text(strip=True) if soup.title else None
    canonical = soup.select_one('link[rel=canonical]')
    result['canonical_url'] = canonical.get('href') if canonical else None
    print('title:', result['title_tag'])
    print('canonical:', result['canonical_url'])
    print('color_context_snippets:', result['color_context_snippets'])
    print('black_context_snippets:', result['black_context_snippets'])
    print('spec_context_snippets:', result['spec_context_snippets'][:8])
    print('embedded_state:', result['embedded_state_evidence'])
else:
    print('FAILED', err)

json.dump(result, open(OUT / 'buds3fe_thorough.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
print('budget after:', budget_status())
