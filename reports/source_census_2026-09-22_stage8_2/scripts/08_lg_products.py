import sys, json
sys.path.insert(0, r'C:\Users\Julynce\AppData\Local\Temp\claude\a--work-dev-product-cards-mvp\9962257a-7031-4112-8b5f-503975d81cc3\scratchpad\stage82')
from lib import fetch, save_fixture, OUT

hosts = ('lg.com', 'www.lg.com')
targets = [
    ('lg_tv', 'https://www.lg.com/kz/tvs-soundbars/4k-uhd-tvs/43um7100plb/'),
    ('lg_washer', 'https://www.lg.com/kz/laundry/washing-machines/f2v5hs2s/'),
]
results = {}
for name, url in targets:
    page, err = fetch(url, hosts, 'product')
    results[name] = {'url': url, 'error': err}
    if page:
        fx = save_fixture(page['struct'])
        s = page['struct']
        results[name].update(fixture=fx, is_product_page=s['is_product_page'], observed=s['observed'],
                              identity=s['contracts']['identity'], specs=s['contracts']['specifications'],
                              media_json_paths=s['contracts']['media']['json_paths'],
                              media_dom=s['contracts']['media']['dom_semantics'],
                              docs=s['contracts']['documents'],
                              cms=[c['engine'] for c in s['cms_fingerprint'] if c['status']=='confirmed'])
        print(name, '-> is_product_page:', s['is_product_page'], 'observed:', s['observed'])
        print('  identity:', json.dumps(s['contracts']['identity'], ensure_ascii=False))
        print('  docs:', json.dumps(s['contracts']['documents'], ensure_ascii=False))
    else:
        print(name, 'FAILED:', err)

json.dump(results, open(OUT / 'lg_products.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
