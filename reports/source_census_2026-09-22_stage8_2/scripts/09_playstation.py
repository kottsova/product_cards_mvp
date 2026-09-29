import sys, json
sys.path.insert(0, r'C:\Users\Julynce\AppData\Local\Temp\claude\a--work-dev-product-cards-mvp\9962257a-7031-4112-8b5f-503975d81cc3\scratchpad\stage82')
from lib import fetch, save_fixture, save_link_index, OUT

hosts = ('playstation.com',)
results = {}
targets = [
    ('ps_controllers_cat', 'https://direct.playstation.com/en-us/accessories/controllers-and-remotes'),
    ('ps_games_cat', 'https://direct.playstation.com/en-us/games/catalog'),
]
for name, url in targets:
    page, err = fetch(url, hosts, 'category')
    results[name] = {'url': url, 'error': err}
    if page:
        fx = save_fixture(page['struct'])
        li = save_link_index(page['struct'], name)
        locs = [l['url'] for l in page['struct']['links']]
        prod = [l['url'] for l in page['struct']['links'] if l['kind'] == 'product']
        results[name].update(fixture=fx, link_index=li, num_links=len(locs), product_links=prod[:15])
        print(name, 'links:', len(locs), 'product-kind:', len(prod))
        for u in locs[:20]:
            print('  ', u)
    else:
        print(name, 'FAILED', err)

json.dump(results, open(OUT / 'playstation_step1.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
