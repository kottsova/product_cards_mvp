"""Stage 10.1 phase 1 -- robots.txt for both hosts (first, before any other request to
that host), then the two already-known root pages, honoring per-host stop conditions."""
import json
from pathlib import Path

from lib import (OUT, RequestLogger, host_of, load_budget, make_probe,
                  parse_robots_disallow, path_disallowed)
from product_tool.census.models import EndpointCapability

budget = load_budget()
allowed_hosts = tuple(budget['allowed_hosts'])
probe = make_probe(budget)
logger = RequestLogger()
stopped_hosts = set()
robots_by_host = {}

for host in allowed_hosts:
    url = f'https://{host}/robots.txt'
    result = probe.probe(url, allowed_hosts=allowed_hosts, capability=EndpointCapability.ROBOTS, sample_type='robots')
    entry = logger.record(url, EndpointCapability.ROBOTS, result)
    if result.access_status.value in ('captcha_or_blocked', 'rate_limited'):
        stopped_hosts.add(host)
        robots_by_host[host] = {'fetched': False, 'disallow': [], 'reason': result.access_status.value}
        continue
    if result.access_status.value != 'direct_access':
        robots_by_host[host] = {'fetched': False, 'disallow': [], 'reason': result.access_status.value, 'http_status': result.http_status}
        continue
    text = getattr(result, 'diagnostic_text', '') or ''
    disallow, seen_star = parse_robots_disallow(text)
    robots_by_host[host] = {
        'fetched': True,
        'http_status': result.http_status,
        'seen_user_agent_star_block': seen_star,
        'disallow_rules': disallow,
        'raw_bytes': entry['bytes_read'],
    }

# Root pages -- already-known seed URLs, not guesses.
root_urls = {'www.xbox.com': 'https://www.xbox.com/', 'support.xbox.com': 'https://support.xbox.com/'}
root_fetch_results = {}
for host, url in root_urls.items():
    if host in stopped_hosts:
        logger.record_skip(url, f'host stopped after robots.txt {robots_by_host[host].get("reason")}')
        continue
    disallow = robots_by_host.get(host, {}).get('disallow_rules', [])
    path = '/'
    if path_disallowed(path, disallow):
        logger.record_skip(url, 'robots.txt disallows /')
        continue
    result = probe.probe(url, allowed_hosts=allowed_hosts, capability=EndpointCapability.HOMEPAGE, sample_type='homepage')
    entry = logger.record(url, EndpointCapability.HOMEPAGE, result)
    if result.access_status.value in ('captcha_or_blocked', 'rate_limited'):
        stopped_hosts.add(host)
    root_fetch_results[host] = {
        'access_status': result.access_status.value,
        'http_status': result.http_status,
        'final_url': result.final_url,
        'bytes_read': entry['bytes_read'],
        'diagnostic_text_len': len(getattr(result, 'diagnostic_text', '') or ''),
    }
    # Save raw bounded text for offline re-analysis.
    (OUT / 'raw').mkdir(parents=True, exist_ok=True)
    safe_name = host.replace('.', '_')
    (OUT / 'raw' / f'{safe_name}_root.html.txt').write_text(getattr(result, 'diagnostic_text', '') or '', encoding='utf-8', errors='replace')

output = {
    'phase': 'robots_and_roots',
    'robots_by_host': robots_by_host,
    'root_fetch_results': root_fetch_results,
    'stopped_hosts': sorted(stopped_hosts),
    'request_log': logger.entries,
    'skipped': logger.rejected,
}
(OUT / 'phase1_robots_and_roots.json').write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding='utf-8')
print(json.dumps({k: v for k, v in output.items() if k != 'request_log'}, indent=2, ensure_ascii=False))
