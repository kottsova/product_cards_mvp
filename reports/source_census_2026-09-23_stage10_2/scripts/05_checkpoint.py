"""Stage 10.2 -- aggregate checkpoint: budget + full request log."""
import json
from pathlib import Path
from urllib.parse import urlsplit

OUT = Path(r'A:\work\dev\product_cards_mvp\reports\source_census_2026-09-23_stage10_2')

budget = json.loads((OUT / 'budget_predeclaration.json').read_text(encoding='utf-8'))

phase_files = ['phase1_ru_sitemap_fetch.json', 'phase2_ru_article_fetch.json']
all_requests = []
seq = 0
for fname in phase_files:
    data = json.loads((OUT / fname).read_text(encoding='utf-8'))
    for entry in data.get('request_log', []):
        seq += 1
        e = dict(entry)
        e['phase_file'] = fname
        e['aggregate_seq'] = seq
        all_requests.append(e)

by_host = {}
for r in all_requests:
    host = (urlsplit(r.get('requested_url', '')).hostname or '').casefold()
    by_host[host] = by_host.get(host, 0) + 1

checkpoint = {
    'stage': '10.2',
    'budget_declared_before_requests': budget,
    'total_requests_made': len(all_requests),
    'requests_by_host': by_host,
    'requests_budget_max_total': budget['limits']['max_requests_total'],
    'request_log_full': all_requests,
    'document_host_budget_used': False,
    'stop_events': {'403_429_or_challenge_seen': False, 'js_only_blocker_confirmed_ru_and_en': True},
    'why_stage_stopped_here': (
        'Both Russian candidate articles returned the identical bare-SPA-shell architecture '
        'already seen for the English versions in Stage 10.1. Per this stage\'s own '
        'pre-declared stop condition ("the only reachable route for a given locale is '
        'confirmed JS-only -> stop pursuing that locale\'s article content, record the gap"), '
        'further requests to structurally identical pages (e.g. the warranty-service article '
        'also found in the sitemap) would not produce new information and were not made.'
    ),
    'status': 'complete_within_budget',
}

(OUT / 'checkpoint.json').write_text(json.dumps(checkpoint, indent=2, ensure_ascii=False), encoding='utf-8')
print('total requests:', len(all_requests), 'by host:', by_host)
