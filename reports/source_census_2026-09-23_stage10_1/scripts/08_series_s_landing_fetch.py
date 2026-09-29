"""Stage 10.1 phase 5 -- fetch the canonical Xbox Series S landing page found
in the official CMS sitemap (not guessed): https://www.xbox.com/en-US/consoles/xbox-series-s"""
import json

from lib import OUT, RequestLogger, load_budget, make_probe
from product_tool.census.models import EndpointCapability

budget = load_budget()
allowed_hosts = tuple(budget['allowed_hosts'])
probe = make_probe(budget)
logger = RequestLogger()

url = 'https://www.xbox.com/en-US/consoles/xbox-series-s'
result = probe.probe(url, allowed_hosts=allowed_hosts, capability=EndpointCapability.PRODUCT_PAGE, sample_type='console_landing_page')
entry = logger.record(url, EndpointCapability.PRODUCT_PAGE, result, note='found via official cms-sitemap-0.xml.gz, not guessed')

text = getattr(result, 'diagnostic_text', '') or ''
(OUT / 'raw' / 'series_s_landing_en_us.html.txt').write_text(text, encoding='utf-8', errors='replace')

output = {
    'phase': 'series_s_landing_fetch',
    'url': url,
    'access_status': result.access_status.value,
    'http_status': result.http_status,
    'final_url': result.final_url,
    'redirect_chain': list(result.redirect_chain),
    'bytes_read': entry['bytes_read'],
    'text_len': len(text),
    'request_log': logger.entries,
}
(OUT / 'phase5_series_s_landing_fetch.json').write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding='utf-8')
print(json.dumps(output, indent=2, ensure_ascii=False))
