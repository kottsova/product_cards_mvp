import sys, json
sys.path.insert(0, r'C:\Users\Julynce\AppData\Local\Temp\claude\a--work-dev-product-cards-mvp\9962257a-7031-4112-8b5f-503975d81cc3\scratchpad\stage82')
from lib import fetch, save_fixture, save_link_index, OUT

hosts = ('lg.com', 'www.lg.com')
results = {}
page, err = fetch('https://www.lg.com/kz/kz-pdp-sitemap-hreflang.xml', hosts, 'sitemap')
results['lg_pdp_sitemap'] = {'url': 'https://www.lg.com/kz/kz-pdp-sitemap-hreflang.xml', 'error': err}
if page:
    fx = save_fixture(page['struct'])
    li = save_link_index(page['struct'], 'lg_pdp_sitemap')
    locs = [l['url'] for l in page['struct']['links']]
    results['lg_pdp_sitemap'].update(fixture=fx, link_index=li, num_links=len(locs))
    print('links', len(locs))
    for u in locs[:15]:
        print(' ', u)

json.dump(results, open(OUT / 'lg_step1.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
