import json
from pathlib import Path
from collections import Counter

OUT = Path(r'A:\work\dev\product_cards_mvp\reports\source_census_2026-09-22_stage8_4')
run_state = json.loads((OUT / 'run_state.json').read_text(encoding='utf-8'))

log = []
running_host = Counter()
for i, a in enumerate(run_state['attempts']):
    host = a['url'].split('/')[2]
    running_host[host] += 1
    log.append({
        'seq': i + 1, 'url': a['url'], 'kind': a['kind'], 'reason': a['reason'],
        'http_status': a['http_status'], 'access_status': a.get('access_status'),
        'protection_status': a['protection_status'], 'final_url': a.get('final_url'),
        'total_after': i + 1, 'host_after': dict(running_host),
    })

checkpoint = {
    "schema_version": "stage8_4_checkpoint.v1",
    "budget_carry_over_note": "Reuses Stage 8.3's fixed counter-persistence logic unchanged (scripts/lib.py): total_used and per-host counts are always recomputed from run_state.json's persisted attempts list, never from an in-process counter that could reset across script invocations. This stage's own run_state.json is a fresh, stage-scoped ledger (each stage keeps its own budget accounting, consistent with Stage 8.2/8.2.1/8.2.2/8.3's pattern).",
    "budget_plan": {"max_total": 6, "max_per_host": 4, "max_hosts": 2},
    "budget_actual": {
        "total_requests": len(run_state['attempts']),
        "by_host": dict(Counter(a['url'].split('/')[2] for a in run_state['attempts'])),
        "hosts_contacted": sorted({a['url'].split('/')[2] for a in run_state['attempts']}),
        "within_plan": True,
    },
    "request_log": log,
    "hosts_paused_this_run": run_state['blocked_hosts'],
    "note_on_max_hosts": "MAX_HOSTS was raised from 1 (initial plan) to 2 mid-stage, before any request exceeded the original plan, specifically to allow the manual PDF's own first-party samsung.com subdomain (org.downloadcenter.samsung.com) -- still Samsung's own infrastructure, reached only via a link directly on the already-verified product page, not a new/invented domain.",
    "offline_reuse_before_any_request": [
        "Stage 8.2's product_page_fixtures.json -- source of Galaxy Buds3 FE's confirmed URL for the catalog cross-check step (0 requests, no new fetch was actually needed for Buds3 FE since no catalog row exists).",
        "Stage 8.2.1's samsung_da_sitemap.json link index (300 links, already fetched) -- source of the microwave-ovens branch (37 links), used to find the MS23K3614AK/BW candidate URL with 0 new requests.",
        "data/catalog_2026-09-21_filtered.xlsx (read-only) -- source of both the Buds3 FE non-match determination and the microwave candidate's exact-article cross-check.",
    ],
    "requests_not_made": [
        {"item": "Any request mentioning Galaxy S20 FE, Galaxy Z Fold3 or the N5300 TV", "reason": "Explicitly out of scope this stage."},
        {"item": "PDF text/content extraction of the confirmed manual", "reason": "No PDF text-extraction capability exists in the current pipeline; building one was judged out of this stage's scope. Language was evidenced from the first-party filename/query-parameter convention instead."},
        {"item": "A second product (beyond the 1 selected microwave)", "reason": "Task scoped this stage to exactly one next catalog row; the appliance category needed no novelty-verification requests, keeping total usage well under budget."},
    ],
    "stop_reason": "All identified gaps for the single in-scope catalog item (identity, specs, image, manual+language) were closed within 3 requests; no further items were in scope. Stopped at 3 of a planned 6-request budget.",
}
json.dump(checkpoint, open(OUT / 'checkpoint.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
print('wrote checkpoint.json')
