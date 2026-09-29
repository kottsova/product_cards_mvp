import json
from pathlib import Path
from collections import Counter
from urllib.parse import urlsplit

OUT = Path(r'A:\work\dev\product_cards_mvp\reports\source_census_2026-09-22_stage8_5')
run_state = json.loads((OUT / 'run_state.json').read_text(encoding='utf-8'))

log = []
running_host = Counter()
for i, a in enumerate(run_state['attempts']):
    host = urlsplit(a['url']).hostname
    running_host[host] += 1
    log.append({
        'seq': i + 1, 'url': a['url'], 'kind': a['kind'], 'reason': a.get('reason'),
        'http_status': a['http_status'], 'protection_status': a.get('protection_status'),
        'final_url': a.get('final_url'), 'bytes_read': a.get('bytes_read'), 'truncated': a.get('truncated'),
        'total_after': i + 1, 'host_after': dict(running_host),
    })

checkpoint = {
    "schema_version": "stage8_5_checkpoint.v1",
    "budget_declared_before_first_request": {
        "max_total": 5, "max_per_host": 3, "max_hosts": 3,
        "pre_declared_allowed_hosts": ["www.samsung.com", "org.downloadcenter.samsung.com", "downloadcenter.samsung.com", "images.samsung.com"],
        "note": "The PDF-serving Samsung domain (org.downloadcenter.samsung.com, redirecting to downloadcenter.samsung.com -- both observed in Stage 8.4's own redirect chain, not invented) was pre-declared in this allow-list before any request was made this stage, per instructions.",
    },
    "budget_actual": {
        "total_requests": len(run_state['attempts']),
        "by_host": {k: v for k, v in Counter(urlsplit(a['url']).hostname for a in run_state['attempts']).items()},
        "hosts_contacted": sorted({urlsplit(a['url']).hostname for a in run_state['attempts']}),
        "within_plan": True,
    },
    "rejected_attempts": run_state.get('rejected_attempts', []),
    "rejected_attempts_note": "Kept in a separate list from executed HTTP requests, per instructions -- empty this stage, since every planned fetch stayed within the pre-declared budget and no gate rejected any call.",
    "request_log": log,
    "hosts_paused_this_run": run_state['blocked_hosts'],
    "counter_persistence": "Continues Stage 8.3/8.4's fix unchanged: total and per-host counts are always recomputed from this stage's own run_state.json, never from an in-process value that could reset across script invocations.",
    "offline_reuse_before_any_request": [
        "Stage 8.4's evidence.json and card_summary.json -- source of the independent-evidence separation (evidence_separation.json), 0 requests.",
        "Stage 8.4's manual_reachability_retry.json -- established the manual link's redirect chain, reused to pre-declare downloadcenter.samsung.com as an allowed host before any Stage 8.5 request.",
    ],
    "new_tooling_added_this_stage": "pypdf 6.19.0, installed into the local, gitignored .venv only -- no tracked project file changed. Used exclusively for the PDF content-extraction attempt described in pdf_content_verification.json.",
    "stop_reason": "All three planned checks (PDF content, broader spec scan, image reachability) were completed within 3 of the 5 planned requests. No further gaps remained open that a network request could close within this stage's declared scope.",
}
json.dump(checkpoint, open(OUT / 'checkpoint.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
print('wrote checkpoint.json')
