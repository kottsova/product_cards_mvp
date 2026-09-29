"""Stage 10.1 phase 7 -- fetch the two Series X|S hardware setup/unboxing support
articles found in support.xbox.com's own en-US sitemap (not guessed)."""
import json

from lib import OUT, RequestLogger, load_budget, make_probe
from product_tool.census.models import EndpointCapability

budget = load_budget()
allowed_hosts = tuple(budget['allowed_hosts'])
probe = make_probe(budget)
logger = RequestLogger()

urls = [
    'https://support.xbox.com/en-US/help/hardware-network/console/unbox-xbox-series-xs-console',
    'https://support.xbox.com/en-US/help/hardware-network/getting-started-set-up/set-up-new-series-x-s',
]

results = {}
for url in urls:
    result = probe.probe(url, allowed_hosts=allowed_hosts, capability=EndpointCapability.SUPPORT_PAGE, sample_type='manual_candidate')
    entry = logger.record(url, EndpointCapability.SUPPORT_PAGE, result, note='found via support.xbox.com en-US sitemap, not guessed')
    text = getattr(result, 'diagnostic_text', '') or ''
    safe = url.rsplit('/', 1)[-1]
    (OUT / 'raw' / f'support_{safe}.html.txt').write_text(text, encoding='utf-8', errors='replace')
    results[url] = {
        'access_status': result.access_status.value,
        'http_status': result.http_status,
        'final_url': result.final_url,
        'bytes_read': entry['bytes_read'],
        'text_len': len(text),
    }

output = {'phase': 'manual_candidates_fetch', 'results': results, 'request_log': logger.entries}
(OUT / 'phase7_manual_candidates_fetch.json').write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding='utf-8')
print(json.dumps(output, indent=2, ensure_ascii=False))
