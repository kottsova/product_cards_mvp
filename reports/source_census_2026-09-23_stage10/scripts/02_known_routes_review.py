"""Stage 10 — offline review of already-saved official sources/routes for Microsoft/Xbox. No network requests."""
import json
from pathlib import Path

ROOT = Path(r'A:\work\dev\product_cards_mvp')
OUT = ROOT / 'reports/source_census_2026-09-23_stage10'

official_domains = json.loads((ROOT / 'product_tool/config/official_domains.v1.json').read_text(encoding='utf-8'))
source_research = json.loads((ROOT / 'product_tool/config/source_research.v1.json').read_text(encoding='utf-8'))
source_catalog = json.loads((ROOT / 'product_tool/config/source_catalog.v2.json').read_text(encoding='utf-8'))
source_candidates = json.loads((ROOT / 'product_tool/config/source_candidates.v1.json').read_text(encoding='utf-8'))

domains_blob = json.dumps(official_domains, ensure_ascii=False).lower()
catalog_blob = json.dumps(source_catalog, ensure_ascii=False).lower()
candidates_blob = json.dumps(source_candidates, ensure_ascii=False).lower()

microsoft_family = next(
    f for f in source_research['families'] if f['source_family_id'] == 'microsoft'
)

result = {
    'registries_checked': [
        'product_tool/config/official_domains.v1.json (17 domains total; production-adjacent research registry with page/support/document host roles)',
        'product_tool/config/source_research.v1.json (per-family research status, incl. support.microsoft.com)',
        'product_tool/config/source_catalog.v2.json (executable production registry)',
        'product_tool/config/source_candidates.v1.json (confirmed-but-non-executable domain candidates)',
    ],
    'official_domains_v1_has_microsoft_or_xbox_entry': (
        'microsoft' in domains_blob or 'xbox' in domains_blob
    ),
    'source_catalog_v2_has_microsoft_or_xbox_entry': (
        'microsoft' in catalog_blob or 'xbox' in catalog_blob
    ),
    'source_candidates_v1_has_microsoft_or_xbox_entry': (
        'microsoft' in candidates_blob or 'xbox' in candidates_blob
    ),
    'source_research_v1_microsoft_family_record': microsoft_family,
    'finding': (
        'No entry for Microsoft/Xbox exists in official_domains.v1.json at all (0 of 17 '
        'entries), and the production source_catalog.v2.json has no Microsoft/Xbox entry '
        'either. The only confirmed official route on file anywhere is support.microsoft.com, '
        'from source_research.v1.json, where it is the sole host listed under both page_hosts '
        'and support_hosts (asset_document_hosts is empty) with source_role="support" and '
        'official_status="official_verified" — but checkpoint.status="pending" (never actually '
        'probed) and endpoint_results=[] (empty) before this stage. There is no host anywhere '
        'in this project\'s registries whose role is "manufacturer" or "retailer" for this '
        'brand family, i.e. no host confirmed to carry commercial product-page content — only '
        'this one support-role domain, which this stage is the first to actually probe. '
        'Its 3 declared probe_targets (all already known, none invented this stage) are: '
        'https://support.microsoft.com/en-us/all-products (support_page), '
        'https://support.microsoft.com/robots.txt (robots_txt), '
        'https://support.microsoft.com/sitemap.xml (sitemap).'
    ),
    'implication_for_this_stage': (
        'Per instructions, new discovery may only use confirmed official sitemap/catalog feed/'
        'internal HTTP search within a pre-declared bounded budget, and must not guess URLs or '
        'endpoints. The only host with any official-verification evidence on file is '
        'support.microsoft.com. This stage therefore restricts allowed_hosts to exactly that '
        'one host for any bounded check, using only the 3 already-declared probe_targets above. '
        'No www.xbox.com, www.microsoft.com/store, or any other Microsoft-owned domain is '
        'assumed, guessed, or added to the allowlist mid-run, even if referenced by text on a '
        'fetched page — a link to such a host would fail AccessProbe\'s redirect/host allowlist '
        'check by design and is treated as an out-of-scope discovery lead for a future stage, '
        'not followed.'
    ),
}

OUT.mkdir(parents=True, exist_ok=True)
(OUT / 'known_routes_review.json').write_text(
    json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8'
)
print(json.dumps({k: v for k, v in result.items() if k not in ('source_research_v1_microsoft_family_record',)}, ensure_ascii=False, indent=2))
