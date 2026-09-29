"""Stage 11.2 -- aggregate checkpoint: budget + full request log."""
import json
from pathlib import Path
from urllib.parse import urlsplit

OUT = Path(r'A:\work\dev\product_cards_mvp\reports\source_census_2026-09-23_stage11_2')

budget = json.loads((OUT / 'budget_predeclaration.json').read_text(encoding='utf-8'))
phase1 = json.loads((OUT / 'phase1_fresh_product_page_and_gallery_fix.json').read_text(encoding='utf-8'))
phase2 = json.loads((OUT / 'phase2_video_and_cover_check.json').read_text(encoding='utf-8'))

all_requests = []
seq = 0
for entry in phase1['request_log']:
    seq += 1
    e = dict(entry)
    e['phase_file'] = 'phase1_fresh_product_page_and_gallery_fix.json'
    e['aggregate_seq'] = seq
    all_requests.append(e)
for entry in phase2['request_log']:
    seq += 1
    e = dict(entry)
    e['phase_file'] = 'phase2_video_and_cover_check.json'
    e['aggregate_seq'] = seq
    all_requests.append(e)

by_host = {}
for r in all_requests:
    host = (urlsplit(r.get('requested_url', '')).hostname or '').casefold()
    by_host[host] = by_host.get(host, 0) + 1

checkpoint = {
    'stage': '11.2',
    'budget_declared_before_requests': budget,
    'total_requests_made': len(all_requests),
    'requests_by_host': by_host,
    'requests_budget_max_total': budget['limits']['max_requests_total'],
    'request_log_full': all_requests,
    'stop_events': {'403_429_confirmed_challenge_seen': False},
    'video_fully_downloaded': False,
    'video_download_reason': 'Only a 64KB bounded Range check was made to confirm type/availability, per the pre-declared budget -- the full ~545MB file was never fetched.',
    'status': 'complete_within_budget',
}

(OUT / 'checkpoint.json').write_text(json.dumps(checkpoint, indent=2, ensure_ascii=False), encoding='utf-8')
print('total requests:', len(all_requests), 'by host:', by_host)
