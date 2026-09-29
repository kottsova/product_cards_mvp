import sys, json
sys.path.insert(0, r'C:\Users\Julynce\AppData\Local\Temp\claude\a--work-dev-product-cards-mvp\9962257a-7031-4112-8b5f-503975d81cc3\scratchpad\stage822')
from lib import fetch, save_fixture, save_link_index, OUT

hosts = ('www.samsung.com',)
url = 'https://www.samsung.com/kz_ru/support/mobile-devices/check-out-the-new-camera-functions-of-galaxy-s20-plus-s20-ultra/'
page, err = fetch(url, hosts, 'support', identity_terms=['Galaxy S20', 'Samsung', 'S20 Ultra', 'S20+'],
                   reason='architectural probe: confirmed first-party support-content link from kz_ru/support/ -- checking whether support CONTENT/article leaf pages render statically, unlike the hub/search pages already found client-rendered. Not the targeted S20 FE/Z Fold3 model (this is an S20 Plus/Ultra camera-feature article) -- used only to test the page-type behavior.')
result = {'url': url, 'error': err}
if page:
    fx = save_fixture(page['struct'])
    li = save_link_index(page['struct'], 'samsung_article_leaf_probe')
    s = page['struct']
    result.update(fixture=fx, link_index=li, is_product_page=s['is_product_page'], observed=s['observed'],
                  identity=s['contracts']['identity'], docs=s['contracts']['documents'],
                  identity_term_matches=page['identity_term_matches'], cms=[c['engine'] for c in s['cms_fingerprint'] if c['status']=='confirmed'])
    print('is_product_page', s['is_product_page'], 'observed', s['observed'])
    print('identity', json.dumps(s['contracts']['identity'], ensure_ascii=False))
    print('identity_term_matches', page['identity_term_matches'])
else:
    print('FAILED', err)
json.dump(result, open(OUT / 'article_leaf_check.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
