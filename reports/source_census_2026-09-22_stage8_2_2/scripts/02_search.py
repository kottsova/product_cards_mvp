import sys, json
from urllib.parse import quote
sys.path.insert(0, r'C:\Users\Julynce\AppData\Local\Temp\claude\a--work-dev-product-cards-mvp\9962257a-7031-4112-8b5f-503975d81cc3\scratchpad\stage822')
from lib import fetch, save_fixture, save_link_index, OUT

hosts = ('www.samsung.com',)
queries = [
    ('samsung_search_s20fe', 'Galaxy S20 FE', 'Galaxy S20 FE 128GB'),
    ('samsung_search_zfold3', 'Galaxy Z Fold3', 'Galaxy Z Fold3 5G 512GB'),
]
results = {}
for name, term, full_catalog_name in queries:
    url = f'https://www.samsung.com/kz_ru/search/?searchvalue={quote(term)}'
    page, err = fetch(url, hosts, 'category', identity_terms=[term, 'Samsung'],
                       reason='confirmed GET search endpoint (searchvalue param) observed directly on the already-fetched kz_ru/support/ page -- query text taken verbatim from the catalog base_model field')
    results[name] = {'url': url, 'term': term, 'catalog_name': full_catalog_name, 'error': err}
    if page:
        fx = save_fixture(page['struct'])
        li = save_link_index(page['struct'], name)
        locs = [l['url'] for l in page['struct']['links']]
        relevant = [u for u in locs if term.split()[-1].lower() in u.lower() or 's20-fe' in u.lower() or 'fold3' in u.lower() or 'fold-3' in u.lower()]
        results[name].update(fixture=fx, link_index=li, num_links=len(locs),
                              is_product_page=page['struct']['is_product_page'],
                              identity_term_matches=page['identity_term_matches'],
                              relevant_links=relevant[:20])
        print(name, 'links', len(locs), 'is_product_page', page['struct']['is_product_page'])
        print('  identity_term_matches', page['identity_term_matches'])
        print('  relevant:', relevant[:20])
    else:
        print(name, 'FAILED', err)

json.dump(results, open(OUT / 'search_check.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
