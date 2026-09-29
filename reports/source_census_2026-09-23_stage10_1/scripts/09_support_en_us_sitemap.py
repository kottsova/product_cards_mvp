"""Stage 10.1 phase 6 -- fetch the en-US child sitemap declared in support.xbox.com's
own sitemap index (found this stage, not guessed), looking for a Series S manual /
quick-start-guide / setup article."""
import json

from lib import OUT, RequestLogger, load_budget, make_probe
from product_tool.census.models import EndpointCapability

budget = load_budget()
allowed_hosts = tuple(budget['allowed_hosts'])
probe = make_probe(budget)
logger = RequestLogger()

url = 'https://support.xbox.com/en-US/sitemap.xml'
result = probe.probe(url, allowed_hosts=allowed_hosts, capability=EndpointCapability.SITEMAP, sample_type='sitemap')
entry = logger.record(url, EndpointCapability.SITEMAP, result)
text = getattr(result, 'diagnostic_text', '') or ''
(OUT / 'raw' / 'support_xbox_com_en_us_sitemap.xml.txt').write_text(text, encoding='utf-8', errors='replace')

import re
locs = re.findall(r'<loc>([^<]+)</loc>', text)

output = {
    'phase': 'support_en_us_sitemap',
    'url': url,
    'access_status': result.access_status.value,
    'http_status': result.http_status,
    'bytes_read': entry['bytes_read'],
    'is_sitemap_index': '<sitemapindex' in text,
    'url_count': len(locs),
    'request_log': logger.entries,
}
(OUT / 'phase6_support_en_us_sitemap.json').write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding='utf-8')
print(json.dumps(output, indent=2, ensure_ascii=False))
