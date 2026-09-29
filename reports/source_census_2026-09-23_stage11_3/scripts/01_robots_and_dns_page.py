"""Stage 11.3 phase 1 -- robots.txt for both DNS hosts, then the user-provided
DNS product page. Checks the page for an explicit model + manufacturer-code
statement before treating it as identity evidence."""
import json
import re

from lib import OUT, RequestLogger, load_budget, make_probe, parse_robots_disallow, path_disallowed
from product_tool.census.models import EndpointCapability

budget = load_budget()
allowed_hosts = tuple(budget['allowed_hosts'])
probe = make_probe(budget)
logger = RequestLogger()

robots_by_host = {}
for host in allowed_hosts:
    url = f'https://{host}/robots.txt'
    result = probe.probe(url, allowed_hosts=allowed_hosts, capability=EndpointCapability.ROBOTS, sample_type='robots')
    logger.record(url, EndpointCapability.ROBOTS, result)
    text = getattr(result, 'diagnostic_text', '') or ''
    (OUT / 'raw').mkdir(parents=True, exist_ok=True)
    (OUT / 'raw' / f'{host.replace(".", "_")}_robots.txt').write_text(text, encoding='utf-8', errors='replace')
    disallow = parse_robots_disallow(text) if result.access_status.value == 'direct_access' else []
    robots_by_host[host] = {'http_status': result.http_status, 'access_status': result.access_status.value, 'disallow': disallow}

page_url = 'https://www.dns-shop.ru/product/driver/e949b555b392d582/mikrofonnyj-komplekt-hyperx-quadcast-2-s-cernyj/'
page_disallow = robots_by_host.get('www.dns-shop.ru', {}).get('disallow', [])
page_path = '/product/driver/e949b555b392d582/mikrofonnyj-komplekt-hyperx-quadcast-2-s-cernyj/'
if path_disallowed(page_path, page_disallow):
    logger.record_skip(page_url, 'robots.txt disallows this path')
    page_result = None
    html = ''
else:
    page_result = probe.probe(page_url, allowed_hosts=allowed_hosts, capability=EndpointCapability.PRODUCT_PAGE, sample_type='dealer_product_page')
    logger.record(page_url, EndpointCapability.PRODUCT_PAGE, page_result, note='exact URL supplied by the user, not guessed')
    html = getattr(page_result, 'diagnostic_text', '') or ''
    (OUT / 'raw' / 'dns_shop_product_page.html.txt').write_text(html, encoding='utf-8', errors='replace')

# Identity check: explicit model name + manufacturer code, not a similar title alone
model_mentions = len(re.findall(r'quadcast\s*2\s*s', html, re.I))
sku_mentions = len(re.findall(r'9A273AA', html, re.I))
pdf_link_present = 'hyperx-quadcast-2-s_instrukcia_104913_30102025.pdf' in html

identity_check = {
    'model_name_quadcast_2s_mentions': model_mentions,
    'manufacturer_code_9A273AA_mentions': sku_mentions,
    'both_present': model_mentions > 0 and sku_mentions > 0,
    'pdf_link_present_on_page': pdf_link_present,
    'conclusion': (
        'identity_confirmed_by_page_content' if (model_mentions > 0 and sku_mentions > 0)
        else 'not_confirmed_insufficient_page_evidence'
    ),
}

output = {
    'phase': 'robots_and_dns_page',
    'robots_by_host': robots_by_host,
    'page_url': page_url,
    'page_http_status': page_result.http_status if page_result else None,
    'page_access_status': page_result.access_status.value if page_result else 'not_fetched',
    'identity_check': identity_check,
    'request_log': logger.entries,
    'skipped': logger.rejected,
}
(OUT / 'phase1_robots_and_dns_page.json').write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding='utf-8')
print(json.dumps({k: v for k, v in output.items() if k not in ('request_log',)}, indent=2, ensure_ascii=False))
