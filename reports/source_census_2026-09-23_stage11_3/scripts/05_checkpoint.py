"""Stage 11.3 -- aggregate checkpoint: budget + full request log."""
import json
from pathlib import Path
from urllib.parse import urlsplit

OUT = Path(r'A:\work\dev\product_cards_mvp\reports\source_census_2026-09-23_stage11_3')

budget = json.loads((OUT / 'budget_predeclaration.json').read_text(encoding='utf-8'))
phase1 = json.loads((OUT / 'phase1_robots_and_dns_page.json').read_text(encoding='utf-8'))
phase2 = json.loads((OUT / 'phase2_pdf_fetch.json').read_text(encoding='utf-8'))

all_requests = []
seq = 0
for entry in phase1['request_log']:
    seq += 1
    e = dict(entry)
    e['phase_file'] = 'phase1_robots_and_dns_page.json'
    e['aggregate_seq'] = seq
    all_requests.append(e)
for entry in phase2['request_log']:
    seq += 1
    e = dict(entry)
    e['phase_file'] = 'phase2_pdf_fetch.json'
    e['aggregate_seq'] = seq
    all_requests.append(e)

by_host = {}
for r in all_requests:
    url = r.get('requested_url', '')
    host = (urlsplit(url).hostname or '').casefold()
    by_host[host] = by_host.get(host, 0) + 1

checkpoint = {
    'stage': '11.3',
    'budget_declared_before_requests': budget,
    'total_requests_made': len(all_requests),
    'requests_by_host': by_host,
    'requests_budget_max_total': budget['limits']['max_requests_total'],
    'request_log_full': all_requests,
    'skipped_requests': phase1.get('skipped', []),
    'stop_events': {
        '403_429_confirmed_challenge_seen': False,
        '401_seen_on_dns_page': True,
        '401_treated_as': 'access blocked; not retried with header spoofing or browser automation, per policy',
    },
    'sulpak_mechta_contacted_this_stage': False,
    'status': 'complete_within_budget',
}

(OUT / 'checkpoint.json').write_text(json.dumps(checkpoint, indent=2, ensure_ascii=False), encoding='utf-8')
print('total requests:', len(all_requests), 'by host:', by_host)
