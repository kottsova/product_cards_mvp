import sys, json
sys.path.insert(0, r'C:\Users\Julynce\AppData\Local\Temp\claude\a--work-dev-product-cards-mvp\9962257a-7031-4112-8b5f-503975d81cc3\scratchpad\stage822')
from lib import fetch, save_fixture, save_link_index, OUT

hosts = ('www.samsung.com',)
targets = [
    ('samsung_manuals_hub', 'https://www.samsung.com/kz_ru/support/user-manuals-and-guide/', 'support'),
    ('samsung_find_your_galaxy', 'https://www.samsung.com/kz_ru/mobile/find-your-galaxy/', 'category'),
]
results = {}
for name, url, kind in targets:
    page, err = fetch(url, hosts, kind, identity_terms=['Galaxy S20 FE', 'Galaxy Z Fold3', 'S20 FE', 'Fold3'],
                       reason='first-party link discovered on the already-fetched kz_ru/support/ page')
    results[name] = {'url': url, 'error': err}
    if page:
        fx = save_fixture(page['struct'])
        li = save_link_index(page['struct'], name)
        locs = [l['url'] for l in page['struct']['links']]
        relevant = [u for u in locs if 's20-fe' in u.lower() or 's20fe' in u.lower() or 'fold3' in u.lower() or 'fold-3' in u.lower() or 'galaxy-s20' in u.lower() or 'galaxy-z-fold3' in u.lower()]
        results[name].update(fixture=fx, link_index=li, num_links=len(locs),
                              is_product_page=page['struct']['is_product_page'],
                              discovery_routes=page['struct']['contracts']['discovery']['routes'],
                              identity_term_matches=page['identity_term_matches'],
                              relevant_links=relevant[:20])
        print(name, 'links', len(locs), 'is_product_page', page['struct']['is_product_page'])
        print('  routes', page['struct']['contracts']['discovery']['routes'])
        print('  identity_term_matches', page['identity_term_matches'])
        print('  relevant:', relevant[:20])
    else:
        print(name, 'FAILED', err)

json.dump(results, open(OUT / 'manuals_finder_check.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
