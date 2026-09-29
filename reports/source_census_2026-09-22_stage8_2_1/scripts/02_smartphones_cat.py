import sys, json
sys.path.insert(0, r'C:\Users\Julynce\AppData\Local\Temp\claude\a--work-dev-product-cards-mvp\9962257a-7031-4112-8b5f-503975d81cc3\scratchpad\stage821')
from lib import fetch, save_fixture, save_link_index, OUT

hosts = ('www.samsung.com',)
url = 'https://www.samsung.com/kz_ru/smartphones/all-smartphones/'
page, err = fetch(url, hosts, 'category', reason='first-party navigation link discovered offline (0 new requests) on the already-known kz_ru homepage snapshot -- /smartphones/ is a real top-level path not covered by the b2c-sitemap.xml branches already checked')
result = {'url': url, 'error': err}
if page:
    fx = save_fixture(page['struct'])
    li = save_link_index(page['struct'], 'samsung_smartphones_cat')
    locs = [l['url'] for l in page['struct']['links']]
    prod = [l['url'] for l in page['struct']['links'] if l['kind'] == 'product' or '/buy/' in l['url']]
    result.update(fixture=fx, link_index=li, num_links=len(locs), product_like_links=prod[:20])
    print('links', len(locs))
    print('product-like:', prod[:20])
else:
    print('FAILED', err)
json.dump(result, open(OUT / 'smartphones_cat_check.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
