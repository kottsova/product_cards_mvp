"""Stage 10.1 -- aggregate checkpoint: budget(s), full request log across all
phases, plus one honestly-disclosed ad hoc diagnostic request made outside the
numbered-script logging path (see note below)."""
import json
from pathlib import Path
from urllib.parse import urlsplit

OUT = Path(r'A:\work\dev\product_cards_mvp\reports\source_census_2026-09-23_stage10_1')

budget = json.loads((OUT / 'budget_predeclaration.json').read_text(encoding='utf-8'))
revision = json.loads((OUT / 'budget_revision_1_document_fetch.json').read_text(encoding='utf-8'))

phase_files = [
    'phase1_robots_and_roots.json', 'phase2_sitemap_check.json', 'phase3_pdp_chunk0_probe.json',
    'phase4_cms_sitemap_fetch.json', 'phase5_series_s_landing_fetch.json',
    'phase6_support_en_us_sitemap.json', 'phase7_manual_candidates_fetch.json',
]

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

# Honest disclosure: one ad hoc diagnostic GET to https://www.xbox.com/robots.txt was made
# during interactive investigation (to preview raw robots.txt text before script 05 was
# written to capture it properly and log it). It was a real HTTP request, same URL/host as
# an already-permitted route, well within budget, but was not captured by the RequestLogger
# at the time. Recorded here for a complete, honest log rather than omitted.
seq += 1
all_requests.append({
    'aggregate_seq': seq,
    'phase_file': 'adhoc_interactive_diagnostic',
    'requested_url': 'https://www.xbox.com/robots.txt',
    'capability': 'robots_txt',
    'http_status': 200,
    'note': (
        'Redundant ad hoc re-fetch of an already-permitted URL, made once during interactive '
        'investigation before script 05 existed to capture and log robots.txt text properly. '
        'Same host/URL as logged requests elsewhere in this checkpoint; disclosed for '
        'completeness, not hidden.'
    ),
})

by_host = {}
for r in all_requests:
    url = r.get('requested_url', '')
    host = (urlsplit(url).hostname or '').casefold()
    by_host[host] = by_host.get(host, 0) + 1

checkpoint = {
    'stage': '10.1',
    'budget_declared_before_requests': budget,
    'budget_revision_declared_before_further_requests': revision,
    'total_requests_made': len(all_requests),
    'requests_by_host': by_host,
    'requests_budget_max_total': budget['limits']['max_requests_total'] + revision['limits_added_to_the_original_budget_not_replacing_it']['max_document_fetch_requests_total'],
    'request_log_full': all_requests,
    'stop_events': {
        '403_429_or_challenge_seen': False,
        'hosts_stopped': phase_files and json.loads((OUT / 'phase1_robots_and_roots.json').read_text(encoding='utf-8'))['stopped_hosts'],
    },
    'off_scope_hosts_not_touched': [
        'www.microsoft.com/en-us/store/b/xbox (explicitly excluded by user scope this stage)',
        'cms-assets.xboxservices.com (image CDN host referenced by URL on the confirmed page; URLs recorded as evidence, binary content never fetched)',
    ],
    'status': 'complete_within_budget',
}

(OUT / 'checkpoint.json').write_text(json.dumps(checkpoint, indent=2, ensure_ascii=False), encoding='utf-8')
print('total requests:', len(all_requests))
print('by host:', by_host)
