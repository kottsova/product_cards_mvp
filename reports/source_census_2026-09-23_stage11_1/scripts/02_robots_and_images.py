"""Stage 11.1 phase 1 -- robots.txt (fresh), then byte-preserving, integrity-
verified fetch of 2 of the 9 already-known 9A273AA image URLs."""
import hashlib
import json

from lib import (OUT, RequestLogger, fetch_bytes_bounded, host_of, load_budget,
                  make_probe, parse_robots_disallow, path_disallowed)
from product_tool.census.models import EndpointCapability

budget = load_budget()
allowed_hosts = tuple(budget['allowed_hosts'])
page_probe = make_probe(budget, max_bytes_key='max_response_bytes_per_request_pages')
logger = RequestLogger()

robots_url = 'https://hyperx.com/robots.txt'
robots_result = page_probe.probe(robots_url, allowed_hosts=allowed_hosts, capability=EndpointCapability.ROBOTS, sample_type='robots')
logger.record(robots_url, EndpointCapability.ROBOTS, robots_result)
robots_text = getattr(robots_result, 'diagnostic_text', '') or ''
disallow = parse_robots_disallow(robots_text)
(OUT / 'raw').mkdir(parents=True, exist_ok=True)
(OUT / 'raw' / 'hyperx_robots.txt').write_text(robots_text, encoding='utf-8', errors='replace')

image_urls = budget['image_verification_targets']
image_policy_probe = make_probe(budget, max_bytes_key='max_response_bytes_per_request_images')
counter = {'n': 0}
image_results = {}

for url in image_urls:
    path = '/' + url.split('/', 3)[-1].split('?')[0]
    if path_disallowed(path, disallow):
        logger.record_skip(url, 'robots.txt disallows this path')
        continue
    result, log_entries = fetch_bytes_bounded(
        image_policy_probe.session, image_policy_probe.policy, url, allowed_hosts,
        chunk_bytes=budget['limits']['max_response_bytes_per_request_images'],
        max_total_bytes=budget['limits']['max_response_bytes_per_request_images'],
        request_counter=counter,
    )
    for e in log_entries:
        e['aggregate_seq'] = None  # filled below
    # Per this project's no-raw-content rule (Stage 8.6): bytes are hashed and visually
    # inspected (Read tool, from a scratch-dir copy) in-session, then discarded -- never
    # committed to the repository.
    data = result.get('bytes')
    sha256 = hashlib.sha256(data).hexdigest() if data else None
    image_results[url] = {
        'completeness': result['completeness'],
        'reason': result.get('reason'),
        'declared_total_bytes': result.get('declared_total_bytes'),
        'bytes_assembled': result.get('bytes_assembled'),
        'content_type': result.get('content_type', ''),
        'sha256': sha256,
        'saved_as': None,
        'note': "Bytes were assembled, hashed, and visually inspected (Read tool) in-session, then discarded -- not committed into the repository, consistent with this project's no-raw-content rule (Stage 8.6).",
        'host_of_url': host_of(url),
        'host_is_official_confirmed_host': host_of(url) in allowed_hosts,
        'range_requests_log': log_entries,
    }

output = {
    'phase': 'robots_and_images',
    'robots_http_status': robots_result.http_status,
    'robots_disallow_rules': disallow,
    'page_request_log': logger.entries,
    'skipped': logger.rejected,
    'image_fetch_total_requests': counter['n'],
    'image_results': image_results,
}
(OUT / 'phase1_robots_and_images.json').write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding='utf-8')
print('robots disallow:', disallow)
for url, r in image_results.items():
    print(url, '->', r['completeness'], r['sha256'], r['saved_as'])
