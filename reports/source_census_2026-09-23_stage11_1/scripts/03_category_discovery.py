"""Stage 11.1 phase 2 -- fetch already-known category pages (found as nav
links on the Stage 8.1/11-confirmed product page) and extract real product
links, to check for candidates matching specific catalog rows."""
import json
import re

from lib import OUT, RequestLogger, load_budget, make_probe
from product_tool.census.models import EndpointCapability

budget = load_budget()
allowed_hosts = tuple(budget['allowed_hosts'])
probe = make_probe(budget, max_bytes_key='max_response_bytes_per_request_pages')
logger = RequestLogger()

category_urls = [
    'https://hyperx.com/collections/gaming-keyboards',
    'https://hyperx.com/collections/gaming-mice',
]

results = {}
for url in category_urls:
    result = probe.probe(url, allowed_hosts=allowed_hosts, capability=EndpointCapability.CATEGORY_PAGE, sample_type='category')
    entry = logger.record(url, EndpointCapability.CATEGORY_PAGE, result, note='already-known nav link from the product page fixture, not guessed')
    text = getattr(result, 'diagnostic_text', '') or ''
    safe = url.rsplit('/', 1)[-1]
    (OUT / 'raw' / f'hyperx_category_{safe}.html.txt').write_text(text, encoding='utf-8', errors='replace')
    product_links = sorted(set(re.findall(r'href="(/products/[a-z0-9\-]+)"', text, re.I)))
    results[url] = {
        'access_status': result.access_status.value,
        'http_status': result.http_status,
        'bytes_read': entry['bytes_read'],
        'product_links_found': product_links,
    }

output = {'phase': 'category_discovery', 'results': results, 'request_log': logger.entries}
(OUT / 'phase2_category_discovery.json').write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding='utf-8')
for url, r in results.items():
    print(url, '->', r['http_status'], len(r['product_links_found']), 'product links')
    for link in r['product_links_found']:
        print('   ', link)
