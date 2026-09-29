import json
from pathlib import Path

OUT = Path(r'A:\work\dev\product_cards_mvp\reports\source_census_2026-09-22_stage8_2_2')


def load(name):
    p = OUT / name
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else None


run_state = load('run_state.json')
support_root = load('support_root_check.json')
search_check = load('search_check.json')
manuals_finder = load('manuals_finder_check.json')
article_leaf = load('article_leaf_check.json')

# ---------------------------------------------------------------------------
# support_routes.json
# ---------------------------------------------------------------------------
support_routes = {
    "schema_version": "stage8_2_2_support_routes.v1",
    "host_confirmation": {
        "host": "www.samsung.com",
        "not_support_samsung_com": True,
        "evidence": [
            "product_tool/config/source_catalog.v2.json: samsung_kz.support_hosts = ['samsung.com']",
            "reports/source_census_2026-09-22_stage8/adapter_profiles.v1.json: samsung_kz_02d9e6.support_hosts = ['www.samsung.com'], samsung_us.support_hosts = ['www.samsung.com']",
            "reports/source_census_2026-09-22_stage8/adapter_profiles.v1.json: samsung_kr.sample_support_page = 'https://www.samsung.com/sec/support/' (already a same-domain, region-path support page, fetched in Stage 8)",
        ],
        "conclusion": "The registry and Stage 8's own evidence both confirm Samsung's support infrastructure lives on the SAME domain (www.samsung.com) under a region path (/sec/support/, /kz_ru/support/, /us/support/), not on a separate support.samsung.com host. support.samsung.com was never assumed and was never contacted.",
    },
    "offline_discovery_before_any_request": [
        {
            "finding": "/kz_ru/support/ is a real first-party link",
            "source": "kz_ru homepage snapshot (Stage 7 sqlite, samsung_kz), reprocessed offline in Stage 8.2.1 and reused here at 0 cost",
        },
        {
            "finding": "/kz_ru/support/user-manuals-and-guide/ is a real first-party link from the same homepage",
            "source": "same offline reprocessing",
        },
        {
            "finding": "samsung.com/sec/support/ (Korea) already has a cached fetch from Stage 8 with 92 links, no manuals-specific link for mobile devices (only a Galaxy Books/laptop download center)",
            "source": "reports/source_census_2026-09-22_stage8/structural_cache.json",
        },
        {
            "finding": "samsung.com/us/ homepage snapshot (Stage 7 sqlite, samsung_us) reprocessed offline: /us/support/downloads/, /us/mobile/find-your-galaxy/, /us/support/ all exist as first-party links",
            "source": "Stage 7 sqlite, reprocessed offline in this stage at 0 cost",
            "note": "Not fetched live this stage (see budget note below); recorded as an evidenced, not-yet-tried regional fallback.",
        },
    ],
    "new_requests": [
        {
            'seq': i + 1,
            'url': a['url'],
            'kind': a['kind'],
            'reason': a['reason'],
            'http_status': a['http_status'],
            'protection_status': a['protection_status'],
            'final_url': a.get('final_url'),
            'redirect_chain': a.get('redirect_chain'),
        }
        for i, a in enumerate(run_state['attempts'])
    ],
    "per_route_findings": {
        "support_root (/kz_ru/support/)": {
            "result": "HTTP 200, ordinary_page. Confirmed a GET search form (route: GET:search:html_search_form) and a live search link with the real parameter name: /kz_ru/search/?searchvalue=mobile. Confirmed first-party links to user-manuals-and-guide/ and mobile/find-your-galaxy/, and to specific support ARTICLE pages (e.g. an S20 Plus/S20 Ultra camera-features article -- not our target FE variant, but proof the /support/mobile-devices/ content section exists).",
            "identity_match": "not applicable (hub page, no single-product claim)",
        },
        "search (/kz_ru/search/?searchvalue=<term>)": {
            "result": "Confirmed real parameter name (searchvalue) reused verbatim from the observed link, not invented. Queried 'Galaxy S20 FE' and 'Galaxy Z Fold3' verbatim from the catalog's base_model field. Both responses: 134 links, generic navigation shell, 0 mention of the search term anywhere in the page text.",
            "identity_match": "Galaxy S20 FE: false. Galaxy Z Fold3: false. Samsung: true (generic brand text only).",
            "conclusion": "Client-side rendered -- same pattern already proven for the main-site search in Stage 8.2.",
        },
        "user-manuals-and-guide hub": {
            "result": "HTTP 200, 135 links, generic navigation shell. 0 mention of S20 FE or Z Fold3 anywhere.",
            "identity_match": "all false except generic 'Samsung' text (not even matched here).",
        },
        "mobile/find-your-galaxy (model finder tool)": {
            "result": "HTTP 200, 139 links, generic navigation shell -- same pattern. The 'model finder' widget itself renders client-side; its result list is not present in the static response.",
            "identity_match": "all false.",
        },
        "support/mobile-devices/<S20-Plus-Ultra-camera-article> (content leaf probe)": {
            "result": "HTTP 200, but STILL client-rendered: 0 JSON-LD/microdata, 0 mention of 'Galaxy S20', 'S20 Ultra' or 'S20+' in the page text (only generic 'Samsung'). This was an architectural probe (not the target model) to check whether support CONTENT pages behave differently from hub pages -- they do not.",
            "identity_match": "Galaxy S20: false, S20 Ultra: false, S20+: false, Samsung: true.",
        },
    },
    "budget_note_and_correction": {
        "planned_caps": {"max_total": 12, "max_per_host": 4, "max_hosts": 3},
        "actual": {"total_requests": len(run_state['attempts']), "www.samsung.com": len(run_state['attempts']), "hosts_contacted": 1},
        "overshoot": "The per-host cap (4) was exceeded: 6 requests were made to www.samsung.com, not 4. Root cause: the bounded-fetch helper script's per-host counter was re-initialized at the start of each of this stage's separate Python invocations (01_support_root.py, 02_search.py, 03_manuals_and_finder.py, 04_article_leaf_check.py) instead of being read back from the persisted run_state.json, so the 4-per-host cap was only enforced within a single script run, not cumulatively across all of them.",
        "corrective_action": "No further requests were made to www.samsung.com or any other host once this was identified. The overall stage-total cap (12) and host-count cap (3) were both respected (6 of 12 used, 1 of 3 hosts contacted). This is disclosed here rather than silently corrected after the fact.",
    },
}
json.dump(support_routes, open(OUT / 'support_routes.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
print('wrote support_routes.json')
