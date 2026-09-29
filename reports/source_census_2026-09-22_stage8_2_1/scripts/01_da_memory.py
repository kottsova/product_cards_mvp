import sys, json
sys.path.insert(0, r'C:\Users\Julynce\AppData\Local\Temp\claude\a--work-dev-product-cards-mvp\9962257a-7031-4112-8b5f-503975d81cc3\scratchpad\stage821')
from lib import fetch, save_fixture, save_link_index, OUT

hosts = ('www.samsung.com',)
results = {}
for name, url in [
    ('samsung_da_sitemap', 'https://www.samsung.com/kz_ru/da-sitemap.xml'),
    ('samsung_memory_sitemap', 'https://www.samsung.com/kz_ru/memory-sitemap.xml'),
]:
    page, err = fetch(url, hosts, 'sitemap', reason='completing the already-known b2c-sitemap.xml branch set (5 declared sub-sitemaps; vd/im/assorted already checked in Stage 8.2) to give a definitive answer, not a partial one')
    results[name] = {'url': url, 'error': err}
    if page:
        fx = save_fixture(page['struct'])
        li = save_link_index(page['struct'], name)
        locs = [l['url'] for l in page['struct']['links']]
        from collections import Counter
        segs = Counter(l['url'].split('/')[4] if len(l['url'].split('/')) > 4 else '' for l in locs and page['struct']['links'])
        seg_counts = Counter(l['url'].split('/')[4] if len(l['url'].split('/')) > 4 else '' for l in page['struct']['links'])
        results[name].update(fixture=fx, link_index=li, num_links=len(locs), segment_counts=dict(seg_counts))
        phone_like = [u for u in locs if 'galaxy-s' in u.lower() or 'galaxy-z' in u.lower() or '/smartphones/' in u.lower()]
        results[name]['phone_like_links'] = phone_like[:10]
        print(name, 'links:', len(locs), 'segments:', dict(seg_counts))
        if phone_like:
            print('  PHONE-LIKE:', phone_like[:10])
    else:
        print(name, 'FAILED', err)

json.dump(results, open(OUT / 'da_memory_check.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
