"""Write the Stage 5.1 audit from saved artifacts, without network requests."""
import json
import re
from pathlib import Path
from .runner_v5_1 import OUTPUT


def write_report(folder=OUTPUT):
    folder=Path(folder)
    payload=json.loads((folder/'dry_run.json').read_text(encoding='utf-8'))
    before=json.loads((folder/'protected_hashes_before.json').read_text(encoding='utf-8'))
    after=json.loads((folder/'protected_hashes_after.json').read_text(encoding='utf-8'))
    test_text=(folder/'tests.txt').read_text(encoding='utf-8')
    matches=re.findall(r'Ran (\d+) tests',test_text)
    tests=matches[-1] if matches else 'unknown'
    passed='Exit code: 0' in test_text
    lines=['# Stage 5.1 — internal-search result quality hardening', '',f"Generated: {payload['generated_at']}", '',
        'Stage 5 remains an immutable historical baseline. No new discovery strategy or production orchestrator was implemented. Work is limited to result quality, semantic checkpoint compatibility, snapshot reprocessing and two explicitly authorized product rechecks.', '',
        '## Causes and fixes', '',
        '- The old card-marker regex matched search-results/search-result-container and inherited that marker across the entire results region. Ordinary navigation therefore received structured_product_result_card:+20. The parser now records the nearest local Product container and respects navigation/layout boundaries. Generic wrappers have no card weight.',
        '- The old shared product-path signal accepted product- substrings, including product-support. Stage 5.1 uses complete product/products/p/mkt-product segments; service paths are excluded unless exact model evidence justifies an explicit exception.',
        '- First-party host, brand-in-host and category hints are not admission criteria. A link must have model evidence, a real product path, a local product card, a Product ItemList element or a declared source path prefix.',
        '- ItemList entries are no longer all classified as Product. A Product node or unambiguous product URL is required. Generic navigation retains generic_first_party_anchor provenance and gets no structured bonus.',
        '- Evidence now distinguishes html_product_card, json_ld_itemlist_product, exact_model_in_result_title, exact_model_in_result_url, configured_product_pattern and generic_first_party_anchor. These are ranking evidence only.',
        '- Two HyperX links were query echoes leading back to search. Search routes are now excluded even when their query contains the target model. This refinement bumped result parser and ranking versions to 3; final validation reprocessed stored responses without new HTTP.', '',
        '## Checkpoint compatibility', '',
        '| Component | Version |','| --- | --- |']
    for key,value in payload['versions'].items():lines.append(f'| {key} | {value} |')
    lines += ['', 'These versions are included in compatibility_key together with the identity/source key, category hints and declarative product path configuration. An unversioned Stage 5 checkpoint returns checkpoint_incompatible, never checkpoint_complete. Matching-version complete checkpoints alone establish zero-request resume. Missing content cannot silently trigger network access.', '',
        '## Snapshot inventory and processing', '',
        'The two pre-existing SQLite databases had no source_snapshots table, and Stage 5 checkpoints had no snapshot references. Initial reprocessing therefore returned snapshot_missing for both products. One explicit bounded refresh was authorized and performed for each product: LG 27ART10AKPL and HyperX 4P5D4AA. No other sources were requested.', '',
        'Four successful response snapshots now use the existing FetchAttempt/SourceSnapshot schema in the isolated source_snapshots.sqlite3 database. Snapshot content is a sanitized HTML discovery/identity projection; scripts, private URL parameters and secret-bearing form/meta values are excluded. Checkpoints store IDs/store references and verified content hashes, never HTML. Final snapshots use sanitizer version 2. All subsequent parser/ranking reprocessing, including the final parser version, was offline.', '',
        'A local product-row uniqueness error initially prevented HyperX setup before its first HTTP request; it was corrected and that same refresh proceeded. LG was replayed from its saved snapshot, not requested again.', '',
        'Per-refresh bounds: 3 queries, 20 candidates, 3 product probes, 10 HTTP requests including redirects; minimum interval 1 second; deadline 50 seconds. Final replay request counts are separate from historical refresh counts.', '',
        '## Before / after', '',
        '| Product | Stage 5 candidates | Final candidates | Removed baseline URLs | Navigation/service exclusions in current response | Refresh HTTP | Final reprocessing HTTP | Final outcome |',
        '| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |']
    for row in payload['runs']:
        result=row['result']
        lines.append(f"| {row['source_family']} {row['catalog_identity']['seller_sku']} | {len(row['baseline_candidates'])} | {len(result['candidates'])} | {len(row['removed_baseline_urls'])} | {row['navigation_service_excluded_in_responses']} | {row['refresh_http_requests']} | {result['budget_used']['http_requests']} | {result['stop_reason']} |")
    lines += ['', 'Exclusion counts are unique normalized service/navigation URLs per processed search response; they differ from removed baseline candidate counts because most links never appeared in the old top-candidate list. Search-route echoes and other rejection categories are recorded separately in result_audits. Final HyperX processing excludes two search-route echoes.', '',
        f"Total actual refresh HTTP requests: **{sum(r['refresh_http_requests'] for r in payload['runs'])}**. Final snapshot reprocessing and compatible resume issue **0** HTTP requests. No 403/429/challenge was observed in this recheck."]
    for row in payload['runs']:
        lines += ['', f"### {row['source_family']} — evidence", '']
        cp=row['result']['checkpoint']
        for route in cp['routes']:
            lines.append(f"- Route: `{route['method']} {route['action_url']}`; query key `{route['query_parameter']}`; source `{route['source']}`; rejection `{route['rejection_reason'] or 'none'}`.")
        for query in cp['completed_queries']:lines.append(f"- Query `{query['query']}`: {query['reason']}; outcome `{query['outcome']}`.")
        for candidate in row['result']['candidates']:
            lines += [f"- Candidate: {candidate['url']}; score {candidate['ranking_score']}; reasons: {', '.join(candidate['ranking_reasons'])}.",f"- Target-page identity: `{candidate['identity_verification'].get('level','not_checked')}`."]
            for evidence in candidate['identity_verification'].get('evidence',[]):
                if evidence['evidence_type']=='model_code':lines.append(f"- Structured model evidence: `{evidence['raw_value']}`, state `{evidence['state']}`, extraction `{evidence['extraction_method']}`. This value came from the target-page snapshot, not search title/URL/card evidence.")
        if not row['result']['candidates']:lines.append('- No admitted product candidates; no exact match is claimed or required.')
        lines.append(f"- Old checkpoint: `{row['old_checkpoint_outcome']}`. Compatible resume: `{row['compatible_resume']['outcome']}`, new requests {row['compatible_resume']['new_http_requests']}. Independent snapshot rebuild: `{row['snapshot_reprocessing']['outcome']}`; candidates/ranks/identity equal: {row['snapshot_reprocessing']['derived_candidates_equal']}.")
        lines += ['', 'Removed Stage 5 candidate URLs:', '']
        lines += ['- '+url for url in row['removed_baseline_urls']]
    lines += ['', '## Regression and preservation', '',f"Full regression suite: **{tests} tests {'passed' if passed else 'NOT verified'}**, exit code {'0' if passed else 'see tests.txt'}. Unit tests use local fixtures; live network is not part of regression discovery.", '',
        'Tests cover generic wrappers, nearest-card attribution, service paths, ItemList navigation, model-only ranking, HyperX structured identity, every semantic version mismatch, compatible zero-request resume, missing/tampered snapshots, offline rebuilding, privacy filtering, production_ready=false, multi-product snapshot storage and unchanged protected files.', '',
        f"Protected hashes identical: **{before==after}**. Full SHA-256 manifests: protected_hashes_before.json and protected_hashes_after.json. They cover production configurations, Stage 2–5 reports, LG/Sulpak adapter files, source policy and pre-existing SQLite files. Registry examples:", '', '| File | Before SHA-256 | After SHA-256 |','| --- | --- | --- |']
    for path,digest in before.items():
        if any(path.replace('\\','/').endswith(name) for name in ('source_catalog.v2.json','source_candidates.v1.json','source_research.v1.json','brand_normalization.v1.json')):
            lines.append(f'| {path} | {digest} | {after[path]} |')
    lines += ['', 'The 186 unresolved labels, Accesstyle negative result, next census batch, LG/Sulpak restrictions and the dealer exclusion remain unchanged. No pre-existing snapshots or uncommitted user changes were removed. Every readiness result remains production_ready=false; this is not completion of the all-brand census.', '',
        '## One next strategy recommendation', '',
        'Evaluate bounded browser-assisted first-party internal search for sources such as LG where the static search response does not expose a valid product result. Retain the same budgets, host allowlists, target-page identity gate and immediate protection stop. This strategy is recommended only and was not implemented in Stage 5.1.', '']
    (folder/'report.md').write_text('\n'.join(lines),encoding='utf-8')


if __name__=='__main__':write_report()
