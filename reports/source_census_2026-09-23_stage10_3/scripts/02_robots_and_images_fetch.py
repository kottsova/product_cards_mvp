"""Stage 10.3 phase 1 -- robots.txt for both asset-CDN hosts, then the two
candidate images identified offline (phase 0), all within the pre-declared
budget."""
import json
import sys
from pathlib import Path

sys.path.insert(0, r'A:\work\dev\product_cards_mvp')

from product_tool.census.endpoint_probe import AccessProbe, ProbePolicy
from product_tool.census.models import EndpointCapability

ROOT = Path(r'A:\work\dev\product_cards_mvp')
OUT = ROOT / 'reports/source_census_2026-09-23_stage10_3'

budget = json.loads((OUT / 'budget_predeclaration.json').read_text(encoding='utf-8'))
allowed_hosts = tuple(budget['allowed_hosts'])
limits = budget['limits']
policy = ProbePolicy(
    timeout_seconds=limits['timeout_seconds_per_request'],
    max_bytes=limits['max_response_bytes_per_request'],
    min_interval_seconds=limits['min_interval_seconds_between_requests'],
)
probe = AccessProbe(policy=policy)

request_log = []


def do_probe(url, capability, sample_type):
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
    }
    request_log.append(entry)
    return result, entry


robots_results = {}
for host in allowed_hosts:
    url = f'https://{host}/robots.txt'
    result, entry = do_probe(url, EndpointCapability.ROBOTS, 'robots')
    text = getattr(result, 'diagnostic_text', '') or ''
    robots_results[host] = {'http_status': result.http_status, 'access_status': result.access_status.value, 'bytes': len(text), 'text_snippet': text[:500]}

output = {
    'phase': 'robots_check',
    'robots_by_host': robots_results,
    'request_log': request_log,
}
(OUT / 'phase1_robots_check.json').write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding='utf-8')
print(json.dumps(robots_results, indent=2, ensure_ascii=False))
