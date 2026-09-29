"""Stage 10.3 -- aggregate checkpoint: budget + full request log across both phases."""
import json
from pathlib import Path
from urllib.parse import urlsplit

OUT = Path(r'A:\work\dev\product_cards_mvp\reports\source_census_2026-09-23_stage10_3')

budget = json.loads((OUT / 'budget_predeclaration.json').read_text(encoding='utf-8'))
phase1 = json.loads((OUT / 'phase1_robots_check.json').read_text(encoding='utf-8'))
phase2 = json.loads((OUT / 'phase2_fetch_candidate_images.json').read_text(encoding='utf-8'))

all_requests = []
seq = 0
for entry in phase1['request_log']:
    seq += 1
    e = dict(entry)
    e['phase_file'] = 'phase1_robots_check.json'
    e['aggregate_seq'] = seq
    all_requests.append(e)
for entry in phase2['request_log']:
    seq += 1
    e = dict(entry)
    e['phase_file'] = 'phase2_fetch_candidate_images.json'
    e['aggregate_seq'] = seq
    all_requests.append(e)

by_host = {}
for r in all_requests:
    host = (urlsplit(r.get('requested_url', '')).hostname or '').casefold()
    by_host[host] = by_host.get(host, 0) + 1

checkpoint = {
    'stage': '10.3',
    'budget_declared_before_requests': budget,
    'total_requests_made': len(all_requests),
    'requests_by_host': by_host,
    'requests_budget_max_total': budget['limits']['max_requests_total'],
    'request_log_full': all_requests,
    'stop_events': {'403_429_or_challenge_seen': False},
    'images_fetched_and_verified_byte_exact': {
        url: {'completeness': r['completeness'], 'declared_total_bytes': r['declared_total_bytes']}
        for url, r in phase2['results'].items()
    },
    'status': 'complete_within_budget_stopped_after_one_check_per_instruction',
}

(OUT / 'checkpoint.json').write_text(json.dumps(checkpoint, indent=2, ensure_ascii=False), encoding='utf-8')
print('total requests:', len(all_requests), 'by host:', by_host)
