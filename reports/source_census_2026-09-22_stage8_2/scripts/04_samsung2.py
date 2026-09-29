import sys, json
sys.path.insert(0, r'C:\Users\Julynce\AppData\Local\Temp\claude\a--work-dev-product-cards-mvp\9962257a-7031-4112-8b5f-503975d81cc3\scratchpad\stage82')
from lib import fetch, save_fixture, save_link_index, OUT

hosts = ('www.samsung.com',)
results = {}
for name, url in [('samsung_vd_sitemap', 'https://www.samsung.com/kz_ru/vd-sitemap.xml'), ('samsung_im_sitemap', 'https://www.samsung.com/kz_ru/im-sitemap.xml')]:
    page, err = fetch(url, hosts, 'sitemap')
    results[name] = {'url': url, 'error': err}
    if page:
        fx = save_fixture(page['struct'])
        li = save_link_index(page['struct'], name)
        locs = [l['url'] for l in page['struct']['links']]
        results[name].update(fixture=fx, link_index=li, num_links=len(locs))
        print(name, 'links:', len(locs))

json.dump(results, open(OUT / 'samsung_step2.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
