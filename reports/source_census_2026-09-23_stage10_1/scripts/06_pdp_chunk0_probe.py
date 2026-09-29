"""Stage 10.1 phase 3 -- fetch exactly one en-US PDP sitemap chunk (chunk 0, the first
one listed in the already-fetched sitemap index) to observe the real URL-slug pattern
before deciding whether a wider (explicitly re-declared) budget is warranted. This stays
within the original budget's max_sitemap_child_documents_per_host=2 (index + this one)."""
import gzip
import json
import re

from lib import OUT, RequestLogger, load_budget, make_probe
from product_tool.census.models import EndpointCapability

budget = load_budget()
allowed_hosts = tuple(budget['allowed_hosts'])
probe = make_probe(budget)
logger = RequestLogger()

url = 'https://www.xbox.com/sitemap/pdp-en-US-sitemap-0.xml.gz'
result = probe.probe(url, allowed_hosts=allowed_hosts, capability=EndpointCapability.SITEMAP, sample_type='sitemap_chunk')
entry = logger.record(url, EndpointCapability.SITEMAP, result)

raw_text = getattr(result, 'diagnostic_text', '') or ''
locs = re.findall(r'<loc>([^<]+)</loc>', raw_text)

output = {
    'phase': 'pdp_chunk0_probe',
    'url': url,
    'access_status': result.access_status.value,
    'http_status': result.http_status,
    'content_type': result.content_type,
    'bytes_read': entry['bytes_read'],
    'looks_gzip_undecoded': raw_text[:2] not in ('<?', '<u'),
    'url_count_found': len(locs),
    'sample_urls': locs[:25],
    'request_log': logger.entries,
}
(OUT / 'phase3_pdp_chunk0_probe.json').write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding='utf-8')
print(json.dumps({k: v for k, v in output.items() if k != 'request_log'}, indent=2, ensure_ascii=False))
