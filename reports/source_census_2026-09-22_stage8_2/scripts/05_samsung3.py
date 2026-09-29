import sys, json
sys.path.insert(0, r'C:\Users\Julynce\AppData\Local\Temp\claude\a--work-dev-product-cards-mvp\9962257a-7031-4112-8b5f-503975d81cc3\scratchpad\stage82')
from lib import fetch, save_fixture, save_link_index, OUT

hosts = ('www.samsung.com',)
results = {}
page, err = fetch('https://www.samsung.com/kz_ru/assorted-sitemap.xml', hosts, 'sitemap')
results['samsung_assorted_sitemap'] = {'url': 'https://www.samsung.com/kz_ru/assorted-sitemap.xml', 'error': err}
if page:
    fx = save_fixture(page['struct'])
    li = save_link_index(page['struct'], 'samsung_assorted_sitemap')
    locs = [l['url'] for l in page['struct']['links']]
    results['samsung_assorted_sitemap'].update(fixture=fx, link_index=li, num_links=len(locs))
    print('links', len(locs))
    kinds = set()
    for l in locs:
        parts = l.split('/')
        if len(parts) > 4:
            kinds.add(parts[4])
    print(sorted(kinds))
    phones = [u for u in locs if 'galaxy-s' in u.lower() or 'smartphone' in u.lower() or '/smartphones/' in u.lower()]
    print('phone-like:', phones[:10])

json.dump(results, open(OUT / 'samsung_step3.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
