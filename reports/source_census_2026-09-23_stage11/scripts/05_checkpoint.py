"""Stage 11 -- aggregate checkpoint: budget + full request log across both phases."""
import json
from pathlib import Path
from urllib.parse import urlsplit

OUT = Path(r'A:\work\dev\product_cards_mvp\reports\source_census_2026-09-23_stage11')

budget = json.loads((OUT / 'budget_predeclaration.json').read_text(encoding='utf-8'))
phase1 = json.loads((OUT / 'phase1_robots_and_product_fetch.json').read_text(encoding='utf-8'))
phase2 = json.loads((OUT / 'phase2_support_page_fetch.json').read_text(encoding='utf-8'))

all_requests = []
seq = 0
for entry in phase1['request_log']:
    seq += 1
    e = dict(entry)
    e['phase_file'] = 'phase1_robots_and_product_fetch.json'
    e['aggregate_seq'] = seq
    all_requests.append(e)
for entry in phase2['request_log']:
    seq += 1
    e = dict(entry)
    e['phase_file'] = 'phase2_support_page_fetch.json'
    e['aggregate_seq'] = seq
    all_requests.append(e)

by_host = {}
for r in all_requests:
    host = (urlsplit(r.get('requested_url', '')).hostname or '').casefold()
    by_host[host] = by_host.get(host, 0) + 1

checkpoint = {
    'stage': 11,
    'budget_declared_before_requests': budget,
    'total_requests_made': len(all_requests),
    'requests_by_host': by_host,
    'requests_budget_max_total': budget['limits']['max_requests_total'],
    'request_log_full': all_requests,
    'stop_events': {
        '403_429_confirmed_challenge_seen': False,
        'challenge_suspected_observed_not_treated_as_stop': any(
            r.get('protection_status') == 'challenge_suspected' for r in all_requests
        ),
    },
    'pdf_document_route_used': False,
    'pdf_document_route_reason': 'No PDF URL was discovered on either fetched page, so Stage 8.6\'s bounded document-fetch mechanism was never invoked -- there was nothing to fetch with it.',
    'why_stage_stopped_here': (
        'The product page and its own confirmed support-page navigation link were both '
        'checked; neither links a PDF or mentions this exact model. Further exploration '
        '(e.g. querying the site\'s own /search?q= form) would move from confirmed navigation '
        'links toward speculative search, which this stage keeps bounded and conservative, '
        'consistent with the rest of this project\'s document-search stages.'
    ),
    'status': 'complete_within_budget',
}

(OUT / 'checkpoint.json').write_text(json.dumps(checkpoint, indent=2, ensure_ascii=False), encoding='utf-8')
print('total requests:', len(all_requests), 'by host:', by_host)
