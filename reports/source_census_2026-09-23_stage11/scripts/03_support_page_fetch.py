"""Stage 11 phase 2 -- fetch the already-confirmed hyperx.com support page
(linked from the product page itself, Stage 8.1's own navigation contract) to
check for any QuadCast 2S-specific manual/PDF link, per the documents
contract's own note: 'a PDF link alone is insufficient' without model-specific
linkage."""
import json
import re

from lib import OUT, RequestLogger, load_budget, make_probe
from product_tool.census.models import EndpointCapability

budget = load_budget()
allowed_hosts = tuple(budget['allowed_hosts'])
probe = make_probe(budget)
logger = RequestLogger()

url = 'https://hyperx.com/pages/support'
result = probe.probe(url, allowed_hosts=allowed_hosts, capability=EndpointCapability.SUPPORT_PAGE, sample_type='support_page')
entry = logger.record(url, EndpointCapability.SUPPORT_PAGE, result, note='already-known nav link from the product page fixture, not guessed')

text = getattr(result, 'diagnostic_text', '') or ''
(OUT / 'raw' / 'hyperx_support_page.html.txt').write_text(text, encoding='utf-8', errors='replace')

pdf_links = sorted(set(re.findall(r'https?://[^\s"\'<>]+\.pdf', text, re.I)))
quadcast_mentions = text.lower().count('quadcast 2 s') + text.lower().count('quadcast 2s') + text.lower().count('quadcast2s')
search_form_present = bool(re.search(r'type=["\']search["\']|name=["\']q["\']', text, re.I))

output = {
    'phase': 'support_page_fetch',
    'url': url,
    'access_status': result.access_status.value,
    'http_status': result.http_status,
    'bytes_read': entry['bytes_read'],
    'pdf_links_found': pdf_links,
    'quadcast_2s_mentions_on_support_page': quadcast_mentions,
    'internal_search_form_present': search_form_present,
    'request_log': logger.entries,
}
(OUT / 'phase2_support_page_fetch.json').write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding='utf-8')
print(json.dumps(output, indent=2, ensure_ascii=False))
