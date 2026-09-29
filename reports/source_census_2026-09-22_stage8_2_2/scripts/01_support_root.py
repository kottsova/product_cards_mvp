import sys, json
sys.path.insert(0, r'C:\Users\Julynce\AppData\Local\Temp\claude\a--work-dev-product-cards-mvp\9962257a-7031-4112-8b5f-503975d81cc3\scratchpad\stage822')
from lib import fetch, save_fixture, save_link_index, OUT

hosts = ('www.samsung.com',)
url = 'https://www.samsung.com/kz_ru/support/'
page, err = fetch(url, hosts, 'support', reason='first-party link discovered offline (0 requests) on the already-known kz_ru homepage snapshot; registry support_hosts for samsung_kz/samsung_kz_02d9e6 both declare www.samsung.com, and Stage 8s own samsung_kr profile already used the same-domain /support/ pattern (samsung.com/sec/support/)')
result = {'url': url, 'error': err}
if page:
    fx = save_fixture(page['struct'])
    li = save_link_index(page['struct'], 'samsung_support_root')
    locs = [l['url'] for l in page['struct']['links']]
    manual_like = [u for u in locs if any(k in u.lower() for k in ['manual','download','model','find','galaxy-s20','galaxy-z-fold','fold3','s20-fe'])]
    search_like = [l for l in page['struct']['links'] if 'search' in l['url'].lower()]
    result.update(fixture=fx, link_index=li, num_links=len(locs),
                  discovery_routes=page['struct']['contracts']['discovery']['routes'],
                  manual_like_links=manual_like[:20], search_like_links=[l['url'] for l in search_like][:10],
                  is_product_page=page['struct']['is_product_page'])
    print('links', len(locs), 'routes:', page['struct']['contracts']['discovery']['routes'])
    print('manual-like:', manual_like[:20])
    print('search-like:', [l['url'] for l in search_like][:10])
else:
    print('FAILED', err)
json.dump(result, open(OUT / 'support_root_check.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
