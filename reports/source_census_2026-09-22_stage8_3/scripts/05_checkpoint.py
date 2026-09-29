import json
from pathlib import Path

OUT = Path(r'A:\work\dev\product_cards_mvp\reports\source_census_2026-09-22_stage8_3')
run_state = json.loads((OUT / 'run_state.json').read_text(encoding='utf-8'))

checkpoint = {
    "schema_version": "stage8_3_checkpoint.v1",
    "bug_fix_from_stage8_2_2": {
        "problem": "Stage 8.2.2's bounded-fetch helper reset its per-host request counter (a plain in-process dict) at the start of every separate script invocation instead of deriving it from the persisted run_state.json, so the stated 4-per-host cap was only enforced within a single script run and was overshot (6 requests to one host against a cap of 4).",
        "fix": "scripts/lib.py now recomputes total_used and per-host counts directly from STATE['attempts'] (loaded from run_state.json) on every single fetch() call, via _recompute_budget_state(). There is no separate counter variable that can drift out of sync with the persisted log.",
        "verified_by": [
            "Empirically in this stage's own run: budget_status() was printed after each of the 2 real fetches, made in 2 SEPARATE Python process invocations (01_buds_refetch.py then 02_buds_thorough.py) against the same run_state.json -- total_used correctly read 1 after the first process and 2 after the second, proving cross-process persistence.",
            "A dedicated regression test, tests/test_structural_census_v8_3.py::BudgetPersistenceTests, which reloads scripts/lib.py fresh (simulating a new script invocation) against a pre-seeded run_state.json containing 4 prior same-host attempts, and asserts the very next fetch() call is rejected with 'host_budget_exhausted' -- proving the cap is read from disk, not from a fresh in-process counter.",
        ],
    },
    "budget_plan": {"max_total": 8, "max_per_host": 4, "max_hosts": 2},
    "budget_actual": {
        "total_requests": len(run_state['attempts']),
        "by_host": {"www.samsung.com": len(run_state['attempts'])},
        "hosts_contacted": 1,
        "within_plan": True,
    },
    "request_log": [
        {'seq': i + 1, 'url': a['url'], 'kind': a['kind'], 'reason': a['reason'],
         'http_status': a['http_status'], 'protection_status': a['protection_status'],
         'total_after': i + 1, 'host_count_after': i + 1}
        for i, a in enumerate(run_state['attempts'])
    ],
    "hosts_paused_this_run": run_state['blocked_hosts'],
    "offline_reuse_before_any_request": [
        "Stage 8.2's product_page_fixtures.json (verified TV + Buds3 FE URLs) -- 0 requests, source of the 2 pilot candidates.",
        "Stage 8.2.1's vd-sitemap.xml / im-sitemap.xml link indexes -- 0 requests, used to confirm TV category taxonomy (full-hd-tv vs. premium tiers) for the novelty check.",
        "Stage 8.2.1's smartphones/all-smartphones category link index -- 0 requests, used to confirm Buds3 FE sits within Samsung's actively-marketed range (galaxy-buds4-pro sibling link).",
        "Stage 8.2.2's support-route findings -- 0 requests, used to justify not re-attempting a manual search for Buds3 FE (same client-rendering wall already proven exhaustively).",
    ],
    "requests_not_made": [
        {"item": "Delivery-Service-TnC.pdf header check", "reason": "Already identified as non-model-specific from its filename and URL path; opening it would not change the 'not an instruction' conclusion, so it was not fetched, conserving budget."},
        {"item": "Any support-route search for a Buds3 FE manual", "reason": "Stage 8.2.2 already exhaustively proved the entire kz_ru support surface is client-rendered regardless of model; a repeat attempt was judged low-value."},
        {"item": "Any request related to Galaxy S20 FE / Galaxy Z Fold3", "reason": "Explicitly out of scope this stage -- Stage 8.2.2's result stands as the historical conclusion for those two models, per instructions."},
    ],
    "stop_reason": "All identified gaps for the single in-scope pilot item (Galaxy Buds3 FE) were closed within 2 requests; the TV was excluded before any network use; no further items remained in scope. Stopped well under the planned 8-request budget.",
}
json.dump(checkpoint, open(OUT / 'checkpoint.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
print('wrote checkpoint.json')
