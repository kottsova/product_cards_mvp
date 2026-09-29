import sys, json, re
sys.path.insert(0, r'C:\Users\Julynce\AppData\Local\Temp\claude\a--work-dev-product-cards-mvp\9962257a-7031-4112-8b5f-503975d81cc3\scratchpad\stage84')
from lib import fetch, save_fixture, save_link_index, OUT, budget_status
from product_tool.census.discovery import json_ld_products, detect_embedded_state
from bs4 import BeautifulSoup

hosts = ('www.samsung.com',)
url = 'https://www.samsung.com/kz_ru/microwave-ovens/solo/ms23k3614akbw/'
page, err = fetch(url, hosts, 'product',
                   identity_terms=['MS23K3614AK', 'Samsung', 'микроволновая', 'Bluetooth', 'IP', 'л', 'Вт'],
                   reason='da-sitemap.xml microwave-ovens branch already discovered offline in Stage 8.2.1 (0 new requests); this URL slug exactly matches catalog article MS23K3614AK/BW -- first live fetch of this specific URL')
result = {'url': url, 'error': err}
if page:
    text = page['raw_text']
    soup = BeautifulSoup(text, 'html.parser')
    fx = save_fixture(page['struct'])
    li = save_link_index(page['struct'], 'samsung_microwave_product')
    result['fixture'] = fx
    result['is_product_page'] = page['struct']['is_product_page']
    result['identity_contract'] = page['struct']['contracts']['identity']
    result['specs_contract'] = page['struct']['contracts']['specifications']
    result['media_contract'] = page['struct']['contracts']['media']
    result['docs_contract'] = page['struct']['contracts']['documents']
    result['cms'] = [c['engine'] for c in page['struct']['cms_fingerprint'] if c['status'] == 'confirmed']
    result['json_ld'] = list(json_ld_products(text))
    result['identity_term_matches'] = page['identity_term_matches']
    result['title_tag'] = soup.title.get_text(strip=True) if soup.title else None
    canonical = soup.select_one('link[rel=canonical]')
    result['canonical_url'] = canonical.get('href') if canonical else None

    pdf_links = []
    for a in soup.select('a[href]'):
        href = a.get('href', '')
        if re.search(r'\.pdf(?:[?#]|$)', href, re.I):
            pdf_links.append({'href': href, 'text': a.get_text(' ', strip=True), 'hreflang': a.get('hreflang')})
    result['pdf_links_found'] = pdf_links

    img_candidates = []
    for tag in soup.select('img[srcset], source[srcset]'):
        img_candidates.append({'srcset': tag.get('srcset'), 'src': tag.get('src'), 'alt': tag.get('alt')})
    result['img_srcset_candidates'] = img_candidates[:15]

    body_text = soup.get_text('\n', strip=True)
    spec_hits = [m.group(0) for m in re.finditer(r'.{0,30}(объем|литр|л\b|вт\b|мощност|гриль|конвекц)\w*.{0,30}', body_text, re.I)][:20]
    result['spec_context_snippets'] = spec_hits
    embedded = detect_embedded_state(text)
    result['embedded_state_evidence'] = [{'kind': e.kind, 'script_id': e.script_id, 'keys': list(e.keys)} for e in embedded]

    print('is_product_page', page['struct']['is_product_page'])
    print('title:', result['title_tag'])
    print('canonical:', result['canonical_url'])
    print('json_ld:', json.dumps(result['json_ld'], ensure_ascii=False)[:2000])
    print('pdf_links:', pdf_links)
    print('img_candidates:', img_candidates[:6])
    print('spec_context_snippets:', spec_hits[:10])
    print('identity_term_matches:', page['identity_term_matches'])
else:
    print('FAILED', err)

json.dump(result, open(OUT / 'microwave_fetch.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
print('budget after:', budget_status())
