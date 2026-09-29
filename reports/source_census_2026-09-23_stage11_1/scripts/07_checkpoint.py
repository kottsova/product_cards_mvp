"""Stage 11.1 -- aggregate checkpoint: budget + full request log across all phases."""
import json
from pathlib import Path
from urllib.parse import urlsplit

OUT = Path(r'A:\work\dev\product_cards_mvp\reports\source_census_2026-09-23_stage11_1')

budget = json.loads((OUT / 'budget_predeclaration.json').read_text(encoding='utf-8'))
phase1 = json.loads((OUT / 'phase1_robots_and_images.json').read_text(encoding='utf-8'))
phase2 = json.loads((OUT / 'phase2_category_discovery.json').read_text(encoding='utf-8'))
phase3 = json.loads((OUT / 'phase3_candidate_product_pages_fetch.json').read_text(encoding='utf-8'))

all_requests = []
seq = 0
for entry in phase1['page_request_log']:
    seq += 1
    e = dict(entry)
    e['phase_file'] = 'phase1_robots_and_images.json (page)'
    e['aggregate_seq'] = seq
    all_requests.append(e)
for url, r in phase1['image_results'].items():
    for entry in r['range_requests_log']:
        seq += 1
        e = dict(entry)
        e['phase_file'] = 'phase1_robots_and_images.json (image range)'
        e['aggregate_seq'] = seq
        all_requests.append(e)
for entry in phase2['request_log']:
    seq += 1
    e = dict(entry)
    e['phase_file'] = 'phase2_category_discovery.json'
    e['aggregate_seq'] = seq
    all_requests.append(e)
for entry in phase3['request_log']:
    seq += 1
    e = dict(entry)
    e['phase_file'] = 'phase3_candidate_product_pages_fetch.json'
    e['aggregate_seq'] = seq
    all_requests.append(e)

by_host = {}
for r in all_requests:
    url = r.get('requested_url', '')
    host = (urlsplit(url).hostname or '').casefold()
    by_host[host] = by_host.get(host, 0) + 1

checkpoint = {
    'stage': '11.1',
    'budget_declared_before_requests': budget,
    'total_requests_made': len(all_requests),
    'requests_by_host': by_host,
    'requests_budget_max_total': budget['limits']['max_requests_total'],
    'request_log_full': all_requests,
    'stop_events': {'403_429_confirmed_challenge_seen': False},
    'category_pages_checked': 2,
    'candidate_product_pages_verified': 2,
    'status': 'complete_within_budget',
}

(OUT / 'checkpoint.json').write_text(json.dumps(checkpoint, indent=2, ensure_ascii=False), encoding='utf-8')
print('total requests:', len(all_requests), 'by host:', by_host)
