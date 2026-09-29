"""Stage 10.1 phase 2 -- sitemap discovery: fetch robots.txt again (raw text this time,
phase 1 only kept the parsed Disallow list) to read any Sitemap: declarations, then try
the declared sitemap or the conventional /sitemap.xml path (same convention already used
for support.microsoft.com in Stage 10) on each non-stopped host."""
import json
import sys
from pathlib import Path

from lib import OUT, RequestLogger, load_budget, make_probe
from product_tool.census.models import EndpointCapability

sys.path.insert(0, r'A:\work\dev\product_cards_mvp')
from product_tool.census.sitemap_strategy import robots_sitemap_declarations

budget = load_budget()
allowed_hosts = tuple(budget['allowed_hosts'])
probe = make_probe(budget)
logger = RequestLogger()

phase1 = json.loads((OUT / 'phase1_robots_and_roots.json').read_text(encoding='utf-8'))
stopped_hosts = set(phase1['stopped_hosts'])

sitemap_findings = {}
for host in allowed_hosts:
    if host in stopped_hosts:
        logger.record_skip(f'https://{host}/robots.txt', 'host previously stopped')
        continue
    url = f'https://{host}/robots.txt'
    result = probe.probe(url, allowed_hosts=allowed_hosts, capability=EndpointCapability.ROBOTS, sample_type='robots_reread_for_sitemap_lines')
    logger.record(url, EndpointCapability.ROBOTS, result, note='re-fetch to capture raw text; phase 1 kept only parsed Disallow rules')
    text = getattr(result, 'diagnostic_text', '') or ''
    (OUT / 'raw' / f'{host.replace(".", "_")}_robots.txt').write_text(text, encoding='utf-8', errors='replace')
    declared = [u for u in robots_sitemap_declarations(text) if host in u]
    sitemap_findings[host] = {'declared_sitemaps': declared}

    candidates = declared or [f'https://{host}/sitemap.xml']
    for sm_url in candidates[:budget['limits']['max_sitemap_child_documents_per_host']]:
        if host in logger.rejected:
            break
        sm_result = probe.probe(sm_url, allowed_hosts=allowed_hosts, capability=EndpointCapability.SITEMAP, sample_type='sitemap')
        entry = logger.record(sm_url, EndpointCapability.SITEMAP, sm_result)
        sitemap_findings[host].setdefault('attempts', []).append({
            'url': sm_url, 'http_status': sm_result.http_status, 'access_status': sm_result.access_status.value,
        })
        if sm_result.access_status.value == 'direct_access' and sm_result.http_status == 200:
            sm_text = getattr(sm_result, 'diagnostic_text', '') or ''
            (OUT / 'raw' / f'{host.replace(".", "_")}_sitemap.xml.txt').write_text(sm_text, encoding='utf-8', errors='replace')
            sitemap_findings[host]['fetched_bytes'] = entry['bytes_read']

output = {
    'phase': 'sitemap_check',
    'sitemap_findings': sitemap_findings,
    'request_log': logger.entries,
    'skipped': logger.rejected,
}
(OUT / 'phase2_sitemap_check.json').write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding='utf-8')
print(json.dumps({k: v for k, v in output.items() if k != 'request_log'}, indent=2, ensure_ascii=False))
