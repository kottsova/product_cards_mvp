"""Stage 10 — bounded, allowlisted probe of the 3 already-known support.microsoft.com routes.

Executes strictly within reports/source_census_2026-09-23_stage10/budget_predeclaration.json:
allowed_hosts = ("support.microsoft.com",), max 6 requests, declared URLs only, plus up to
3 same-host candidate links discovered on the support page (never off-host).
"""
import json
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit

sys.path.insert(0, r'A:\work\dev\product_cards_mvp')

from product_tool.census.endpoint_probe import AccessProbe, ProbePolicy
from product_tool.census.models import EndpointCapability

ROOT = Path(r'A:\work\dev\product_cards_mvp')
OUT = ROOT / 'reports/source_census_2026-09-23_stage10'

budget = json.loads((OUT / 'budget_predeclaration.json').read_text(encoding='utf-8'))
allowed_hosts = tuple(budget['allowed_hosts'])
max_requests = budget['limits']['max_requests_total']
max_follow = budget['limits']['max_candidate_links_followed_from_support_page']

policy = ProbePolicy(
    timeout_seconds=budget['limits']['timeout_seconds_per_request'],
    max_bytes=budget['limits']['max_response_bytes_per_request'],
    min_interval_seconds=budget['limits']['min_interval_seconds_between_requests'],
)
probe = AccessProbe(policy=policy)

request_log = []
rejected_off_host_links = []


def do_probe(url, capability, sample_type):
    if len(request_log) >= max_requests:
        return None
    result = probe.probe(url, allowed_hosts=allowed_hosts, capability=capability, sample_type=sample_type)
    entry = {
        'seq': len(request_log) + 1,
        'requested_url': url,
        'capability': capability.value if hasattr(capability, 'value') else str(capability),
        'access_status': result.access_status.value,
        'http_status': result.http_status,
        'final_url': result.final_url,
        'redirect_chain': list(result.redirect_chain),
        'content_type': result.content_type,
        'protection_status': result.protection_status.value,
        'error': result.error,
        'bytes_evidence': [e for e in result.evidence if e.get('type') == 'bounded_get'],
    }
    request_log.append(entry)
    return result


# 1) robots.txt (already-known route)
robots_result = do_probe('https://support.microsoft.com/robots.txt', EndpointCapability.ROBOTS, 'robots')

# 2) sitemap.xml (already-known route)
sitemap_result = do_probe('https://support.microsoft.com/sitemap.xml', EndpointCapability.SITEMAP, 'sitemap')

# 3) the all-products support page (already-known route)
support_result = do_probe('https://support.microsoft.com/en-us/all-products', EndpointCapability.HOMEPAGE, 'support')

diagnostic_text = getattr(support_result, 'diagnostic_text', '') if support_result else ''

# Same-host candidate links mentioning xbox, ranked by relevance; off-host links are recorded, not followed.
candidate_links = []
if diagnostic_text:
    for m in re.finditer(r'href=["\']([^"\']+)["\']', diagnostic_text, re.I):
        href = m.group(1)
        absolute = urljoin(support_result.final_url or 'https://support.microsoft.com/en-us/all-products', href)
        host = (urlsplit(absolute).hostname or '').casefold()
        if 'xbox' not in absolute.lower():
            continue
        if host == 'support.microsoft.com':
            if absolute not in candidate_links:
                candidate_links.append(absolute)
        else:
            if absolute not in rejected_off_host_links:
                rejected_off_host_links.append(absolute)

candidate_links = candidate_links[:max_follow]
followed_results = []
for link in candidate_links:
    if len(request_log) >= max_requests:
        break
    r = do_probe(link, EndpointCapability.PRODUCT_PAGE if hasattr(EndpointCapability, 'PRODUCT_PAGE') else EndpointCapability.HOMEPAGE, 'candidate_link')
    followed_results.append({'url': link, 'access_status': r.access_status.value if r else None})

output = {
    'executed_at': '2026-09-23',
    'budget_reference': 'budget_predeclaration.json',
    'allowed_hosts': list(allowed_hosts),
    'request_log': request_log,
    'total_requests_made': len(request_log),
    'candidate_xbox_links_found_on_support_page_same_host': candidate_links,
    'candidate_links_followed_results': followed_results,
    'off_host_links_seen_but_not_followed': rejected_off_host_links[:20],
    'off_host_links_total_seen': len(rejected_off_host_links),
    'stop_reason': (
        'budget_exhausted' if len(request_log) >= max_requests
        else 'all_declared_and_discovered_same_host_candidates_exhausted'
    ),
}

(OUT / 'bounded_probe_result.json').write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding='utf-8')

# Save raw (bounded, truncated) page text for offline re-analysis, per project convention.
if support_result is not None:
    (OUT / 'raw').mkdir(parents=True, exist_ok=True)
    (OUT / 'raw' / 'support_all_products.html.txt').write_text(diagnostic_text or '', encoding='utf-8', errors='replace')

print(json.dumps({k: v for k, v in output.items() if k not in ('request_log',)}, ensure_ascii=False, indent=2))
print('requests made:', len(request_log))
