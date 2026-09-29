import sys, json, re
sys.path.insert(0, r'C:\Users\Julynce\AppData\Local\Temp\claude\a--work-dev-product-cards-mvp\9962257a-7031-4112-8b5f-503975d81cc3\scratchpad\stage83')
from lib import fetch, save_fixture, save_link_index, OUT, budget_status
from product_tool.census.discovery import json_ld_products

hosts = ('www.samsung.com',)
url = 'https://www.samsung.com/kz_ru/audio-sound/galaxy-buds/galaxy-buds3-fe-black-sm-r420nzkacis/'
page, err = fetch(url, hosts, 'product', identity_terms=['Galaxy Buds3 FE', 'Buds3 FE', 'Samsung'],
                   reason='re-fetch of the SAME URL already confirmed as a verified Product page in Stage 8.2 -- not new discovery. Needed because the Stage 8.2 structural census fixture deliberately records field NAMES/PATHS only (.name, .sku), never actual field VALUES, so no real product-card content (actual name text, color, specs, image URL, manual link) exists in any offline evidence for this page.')
result = {'url': url, 'error': err, 'budget_after': budget_status()}
if page:
    fx = save_fixture(page['struct'])
    li = save_link_index(page['struct'], 'buds3fe_product_refetch')
    products = list(json_ld_products(page['raw_text']))
    result['json_ld_products_raw'] = products
    result['is_product_page'] = page['struct']['is_product_page']
    result['identity_term_matches'] = page['identity_term_matches']
    result['fixture'] = fx
    # extract PDF/document links directly from the page for card evidence
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(page['raw_text'], 'html.parser')
    pdf_links = []
    for a in soup.select('a[href]'):
        href = a.get('href', '')
        if re.search(r'\.pdf(?:[?#]|$)', href, re.I):
            pdf_links.append({'href': href, 'text': a.get_text(' ', strip=True), 'hreflang': a.get('hreflang')})
    result['pdf_links_found'] = pdf_links
    # extract responsive image candidates
    img_candidates = []
    for tag in soup.select('img[srcset], source[srcset]'):
        img_candidates.append({'srcset': tag.get('srcset'), 'src': tag.get('src'), 'alt': tag.get('alt')})
    result['img_srcset_candidates'] = img_candidates[:10]
    print('is_product_page', page['struct']['is_product_page'])
    print('json_ld_products:', json.dumps(products, ensure_ascii=False)[:3000])
    print('pdf_links:', pdf_links)
    print('identity_term_matches', page['identity_term_matches'])
else:
    print('FAILED', err)

json.dump(result, open(OUT / 'buds3fe_refetch.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
print('budget after:', budget_status())
