"""Stage 11.1 phase 3 -- fetch the two candidate product pages found in
phase 2's category discovery (not guessed), matching catalog rows for a
keyboard and a mouse. Extract identity/specifications/media/documents
contracts independently for each, and compare each page's inspect_structure()
signature against Stage 8.1's HyperX fixture signature."""
import json

from lib import OUT, RequestLogger, load_budget, make_probe
from product_tool.census.models import EndpointCapability
from product_tool.census.discovery import json_ld_products
from product_tool.census.structural_contracts_v8 import inspect_structure

budget = load_budget()
allowed_hosts = tuple(budget['allowed_hosts'])
probe = make_probe(budget, max_bytes_key='max_response_bytes_per_request_pages')
logger = RequestLogger()

ROOT_HOSTS = ('hyperx.com',)
STAGE8_1_SIGNATURES = {
    "discovery": "3a37e3368e1918adccc33346dc514b54a965a64f7f66d8e78f82e9913af91193",
    "identity": "bf9c35cd62d2db8c606ef87b32c1650ad87e8e1c5755cdce1e19a500018405d3",
    "specifications": "75569a5e2ebb535fc7f272a21112732ee32f7b5c50bd139acf4df3f5edc7649c",
    "media": "010a9dc655a92cd056a73b259bc37615c36e41db00f04be938a4b2a10ae756f4",
    "documents": "2623905769e9dff909a0abd83924d855e6877e185d0b78ccb7446028fca7b4be",
}

candidates = {
    'keyboard': 'https://hyperx.com/products/hyperx-alloy-rise-75-mechanical-gaming-keyboard',
    'mouse': 'https://hyperx.com/products/hyperx-pulsefire-fuse-wireless-gaming-mouse',
}

results = {}
for kind, url in candidates.items():
    result = probe.probe(url, allowed_hosts=allowed_hosts, capability=EndpointCapability.PRODUCT_PAGE, sample_type=f'product_page_{kind}')
    entry = logger.record(url, EndpointCapability.PRODUCT_PAGE, result, note='found via category page in phase 2, not guessed')
    html = getattr(result, 'diagnostic_text', '') or ''
    (OUT / 'raw' / f'hyperx_{kind}_product_page.html.txt').write_text(html, encoding='utf-8', errors='replace')

    products = json_ld_products(html)
    structure = inspect_structure(html, url, ROOT_HOSTS)
    signature_match = {k: structure['signatures'].get(k) == v for k, v in STAGE8_1_SIGNATURES.items()}

    results[kind] = {
        'url': url,
        'access_status': result.access_status.value,
        'http_status': result.http_status,
        'bytes_read': entry['bytes_read'],
        'is_product_page_per_inspect_structure': structure['is_product_page'],
        'contract_signature_match_vs_stage8_1_microphone_fixture': signature_match,
        'contract_signature_match_all': all(signature_match.values()),
        'json_ld_product_count': len(products),
        'json_ld_products_raw': products,
    }

output = {'phase': 'candidate_product_pages_fetch', 'results': results, 'request_log': logger.entries}
(OUT / 'phase3_candidate_product_pages_fetch.json').write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding='utf-8')
for kind, r in results.items():
    print(kind, r['url'], '->', r['http_status'], 'products:', r['json_ld_product_count'], 'sig_match:', r['contract_signature_match_all'])
    if r['json_ld_products_raw']:
        p = r['json_ld_products_raw'][0]
        print('   name:', p.get('name'), '| sku:', p.get('sku'), '| additionalProperty count:', len(p.get('additionalProperty', [])))
