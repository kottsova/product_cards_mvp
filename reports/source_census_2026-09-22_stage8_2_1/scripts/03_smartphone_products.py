import sys, json
sys.path.insert(0, r'C:\Users\Julynce\AppData\Local\Temp\claude\a--work-dev-product-cards-mvp\9962257a-7031-4112-8b5f-503975d81cc3\scratchpad\stage821')
from lib import fetch, save_fixture, OUT

hosts = ('www.samsung.com',)
targets = [
    ('samsung_phone_s25ultra', 'https://www.samsung.com/kz_ru/smartphones/galaxy-s25-ultra/', 'category_or_product'),
    ('samsung_phone_s26ultra_buy', 'https://www.samsung.com/kz_ru/smartphones/galaxy-s26-ultra/buy/', 'product'),
]
results = {}
for name, url, kind in targets:
    page, err = fetch(url, hosts, 'product', identity_terms=['Galaxy S25 Ultra', 'Galaxy S26 Ultra', 'Samsung'],
                       reason='first-party link from the already-fetched smartphones/all-smartphones category page')
    results[name] = {'url': url, 'error': err}
    if page:
        fx = save_fixture(page['struct'])
        s = page['struct']
        results[name].update(fixture=fx, is_product_page=s['is_product_page'], observed=s['observed'],
                              identity=s['contracts']['identity'], specs=s['contracts']['specifications'],
                              media_json_paths=s['contracts']['media']['json_paths'],
                              media_dom=s['contracts']['media']['dom_semantics'],
                              docs=s['contracts']['documents'],
                              cms=[c['engine'] for c in s['cms_fingerprint'] if c['status']=='confirmed'],
                              identity_term_matches=page['identity_term_matches'])
        print(name, '-> is_product_page:', s['is_product_page'], 'observed:', s['observed'])
        print('  identity:', json.dumps(s['contracts']['identity'], ensure_ascii=False))
        print('  identity_term_matches:', page['identity_term_matches'])
    else:
        print(name, 'FAILED', err)

json.dump(results, open(OUT / 'smartphone_products.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
