import sys, time, json, re
sys.path.insert(0, r'C:\Users\Julynce\AppData\Local\Temp\claude\a--work-dev-product-cards-mvp\9962257a-7031-4112-8b5f-503975d81cc3\scratchpad\stage82')
from lib import fetch, save_fixture, OUT

hosts = ('www.samsung.com',)
results = {}

# Step 1: descend the already-known sitemap index (kz_ru) to find b2c-sitemap.xml
page, err = fetch('https://www.samsung.com/kz_ru/b2c-sitemap.xml', hosts, 'sitemap')
results['step1_b2c_sitemap'] = {'url': 'https://www.samsung.com/kz_ru/b2c-sitemap.xml', 'error': err}
if page:
    fx = save_fixture(page['struct'])
    locs = [l['url'] for l in page['struct']['links']]
    results['step1_b2c_sitemap'].update(fixture=fx, num_links=len(locs), sample_links=locs[:20])
    print('b2c-sitemap.xml links:', len(locs))
    for u in locs[:20]:
        print(' ', u)

json.dump(results, open(OUT / 'samsung_step1.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
