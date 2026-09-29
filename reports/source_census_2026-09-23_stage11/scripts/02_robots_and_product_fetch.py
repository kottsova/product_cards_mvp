"""Stage 11 phase 1 -- robots.txt then the already-confirmed HyperX product
page, within the pre-declared budget. Extracts actual JSON-LD Product values
(not just the sanitized contract) and re-runs inspect_structure() to confirm
this fresh page's contract signature still matches Stage 8.1's fixture before
trusting it for extraction."""
import json
import sys

sys.path.insert(0, r'A:\work\dev\product_cards_mvp')

from lib import OUT, RequestLogger, load_budget, make_probe
from product_tool.census.models import EndpointCapability
from product_tool.census.discovery import json_ld_products
from product_tool.census.structural_contracts_v8 import inspect_structure

ROOT_HOSTS = ('hyperx.com',)

budget = load_budget()
allowed_hosts = tuple(budget['allowed_hosts'])
probe = make_probe(budget)
logger = RequestLogger()

# 1) robots.txt first
robots_url = 'https://hyperx.com/robots.txt'
robots_result = probe.probe(robots_url, allowed_hosts=allowed_hosts, capability=EndpointCapability.ROBOTS, sample_type='robots')
logger.record(robots_url, EndpointCapability.ROBOTS, robots_result)

# 2) the already-confirmed product page
product_url = budget['seed_url_already_known_not_guessed']
product_result = probe.probe(product_url, allowed_hosts=allowed_hosts, capability=EndpointCapability.PRODUCT_PAGE, sample_type='product_page')
entry = logger.record(product_url, EndpointCapability.PRODUCT_PAGE, product_result, note='same URL as Stage 8.1 fixture 1dd3897...')

html = getattr(product_result, 'diagnostic_text', '') or ''
(OUT / 'raw').mkdir(parents=True, exist_ok=True)
(OUT / 'raw' / 'hyperx_quadcast_2s_product_page.html.txt').write_text(html, encoding='utf-8', errors='replace')

products = json_ld_products(html)
structure = inspect_structure(html, product_url, ROOT_HOSTS)

stage8_1_signatures = {
    "discovery": "3a37e3368e1918adccc33346dc514b54a965a64f7f66d8e78f82e9913af91193",
    "identity": "bf9c35cd62d2db8c606ef87b32c1650ad87e8e1c5755cdce1e19a500018405d3",
    "specifications": "75569a5e2ebb535fc7f272a21112732ee32f7b5c50bd139acf4df3f5edc7649c",
    "media": "010a9dc655a92cd056a73b259bc37615c36e41db00f04be938a4b2a10ae756f4",
    "documents": "2623905769e9dff909a0abd83924d855e6877e185d0b78ccb7446028fca7b4be",
}
signature_match = {k: structure['signatures'].get(k) == v for k, v in stage8_1_signatures.items()}

output = {
    'phase': 'robots_and_product_fetch',
    'robots_access_status': robots_result.access_status.value,
    'robots_http_status': robots_result.http_status,
    'product_access_status': product_result.access_status.value,
    'product_http_status': product_result.http_status,
    'product_final_url': product_result.final_url,
    'product_redirect_chain': list(product_result.redirect_chain),
    'bytes_read': entry['bytes_read'],
    'is_product_page_per_inspect_structure': structure['is_product_page'],
    'contract_signature_match_vs_stage8_1': signature_match,
    'contract_signature_match_all': all(signature_match.values()),
    'json_ld_product_count': len(products),
    'json_ld_products_raw': products,
    'request_log': logger.entries,
}
(OUT / 'phase1_robots_and_product_fetch.json').write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding='utf-8')
print('http_status:', product_result.http_status, 'access_status:', product_result.access_status.value)
print('signature_match_all:', output['contract_signature_match_all'])
print('json_ld_products found:', len(products))
if products:
    print(json.dumps(products[0], indent=2, ensure_ascii=False)[:2000])
