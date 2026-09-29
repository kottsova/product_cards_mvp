"""Stage 5 opt-in dry-run: one catalog sample per first-party source family."""
from __future__ import annotations
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

from .catalog import load_catalog_coverage
from .endpoint_probe import guarded_entry_point
from .registry import load_source_catalog
from .runner_v4 import DryRunSource, _sample_products, _source_specs
from .internal_search_strategy import InternalSearchStrategy, internal_search_readiness
from .search_routes import QUERY_NAMES, now
from .sitemap_strategy import DiscoveryBudget

ROOT = Path(__file__).resolve().parents[2]


def protected_hashes():
    paths = list((ROOT / 'product_tool/config').glob('*.json'))
    paths += [ROOT/'product_tool/sources.py', ROOT/'product_tool/adapters/lg.py', ROOT/'product_tool/adapters/sulpak.py']
    for stage in (2, 3, 4):
        paths += [p for p in (ROOT/f'reports/source_census_2026-09-22_stage{stage}').rglob('*') if p.is_file()]
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}


def source_specs():
    lg = next(r for r in load_source_catalog().records if r.source_id == 'lg_kz')
    return (DryRunSource('lg_kz', 'LG', lg.candidate_url, lg.page_hosts, (), 'source_catalog.v2'), *_source_specs())


def configured_routes(source):
    # Only recorded endpoints with an explicit query key; never synthesize paths.
    from .candidates import load_source_candidates
    from .research import load_source_research
    records = [*load_source_catalog().records, *load_source_candidates().records]
    targets = [t for r in records if r.candidate_url == source.source_url for t in r.probe_targets]
    targets += [t for r in load_source_research()['families'] if r['source_family_id'] == source.source_family for t in r['probe_targets']]
    result = []
    for target in targets:
        if target.get('capability') != 'internal_search':
            continue
        url = target['url']
        keys = [k for k, v in parse_qsl(urlsplit(url).query, keep_blank_values=True) if k.lower() in QUERY_NAMES]
        result.append({'url': url, 'method': target.get('method', 'GET'), 'query_parameter': keys[0] if len(set(keys)) == 1 else ''})
    return tuple(result)


def write_json(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    temporary.replace(path)


def run_stage5_dry_run(catalog_path, output_dir, *, refresh=False, strategy_factory=InternalSearchStrategy):
    catalog_path = Path(catalog_path)
    if catalog_path.resolve() != (ROOT/'data/catalog_2026-09-21_filtered.xlsx').resolve():
        raise ValueError('Stage 5 only accepts the designated filtered catalog')
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    before = protected_hashes()
    census = load_catalog_coverage(catalog_path)
    checkpoint_path = output_dir/'checkpoint.json'
    cp = json.loads(checkpoint_path.read_text(encoding='utf-8')) if checkpoint_path.exists() else {'schema_version':1, 'runs':{}}
    budget = DiscoveryBudget(max_http_requests=10, max_product_candidates=20, max_product_pages=3, min_interval_seconds=1.0, deadline_seconds=50)
    runs = []
    for source in source_specs():
        samples = _sample_products(census, source, limit=1)
        if not samples:
            runs.append({'source_family': source.source_family, 'stop_reason':'no_catalog_sample'})
            continue
        expected = samples[0]
        key = source.source_family+':'+expected.seller_sku
        def save(value):
            cp['runs'][key] = value
            cp['updated_at'] = now()
            write_json(checkpoint_path, cp)
        kwargs = dict(source_family=source.source_family, source_url=source.source_url, allowed_hosts=source.allowed_hosts, expected=expected, configured_endpoints=configured_routes(source), category_hints=(expected.category_raw,))
        result = strategy_factory(budget=budget).run(**kwargs, checkpoint=cp['runs'].get(key), refresh=refresh, checkpoint_callback=save)
        # Check replay with a new strategy instance: must produce no network work.
        resumed = strategy_factory(budget=budget).run(**kwargs, checkpoint=result.checkpoint)
        runs.append({'source_family': source.source_family, 'source_url':source.source_url, 'source_origin':source.origin, 'catalog_identity':expected.to_dict(), 'result':result.to_dict(), 'readiness':internal_search_readiness(result), 'resume_verification':{'stop_reason':resumed.stop_reason, 'new_http_requests':resumed.budget_used.http_requests-result.budget_used.http_requests, 'checkpoint_unchanged':resumed.checkpoint == result.checkpoint}})
        print(f"{source.source_family}: {result.stop_reason}; HTTP={result.budget_used.http_requests}; candidates={len(result.candidates)}", flush=True)
        write_json(output_dir/'partial_runs.json', {'runs':runs})
    after = protected_hashes()
    payload = {'schema_version':1, 'strategy':'internal_search', 'generated_at':now(), 'catalog_path':str(catalog_path), 'catalog_sha256':hashlib.sha256(catalog_path.read_bytes()).hexdigest(), 'budget':asdict(budget), 'hard_caps':{'queries':3, 'candidates':20, 'product_pages':3, 'http_requests_including_redirects':10}, 'runs':runs, 'production_registry_unchanged':before==after, 'protected_hashes_before':before, 'protected_hashes_after':after}
    write_json(output_dir/'dry_run.json', payload)
    write_report(output_dir, payload)
    if before != after:
        raise RuntimeError('Protected registry/report files changed during dry-run')
    return payload


def write_report(output_dir, payload):
    old = json.loads((ROOT/'reports/source_census_2026-09-22_stage4/dry_run.json').read_text(encoding='utf-8'))
    sitemap = {r['source_family']:r for r in old['runs']}
    lines = ['# Stage 5 — bounded internal-search discovery v1', '', f"Generated: {payload['generated_at']}", '',
        'Reuses DiscoveryBudget, BudgetUsage, CandidatePage, StrategyResult, URL normalization, host allowlists, AccessProbe and structured IdentityVerifier. StrategyResult now carries strategy and strategy_evidence. SearchRoute records action, method, query key, constants, origin, allowed host, confidence, rejection and timestamp. Historical census serialization remains compatible.', '',
        'Automatic routes are declared GET only. POST, account/cart/login, password/file fields, CSRF/session keys, JavaScript handlers, unconfigured APIs and foreign hosts are rejected as manual_or_future_strategy. Scripts are never executed or used to invent routes. Hidden parameters outside a small static search/locale allowlist require review.', '',
        'Per source hard caps: 3 queries, 20 retained candidates, 3 product probes, 10 actual HTTP requests including redirects; 1 second minimum interval; 50 second deadline; bounded response/parser sizes. Each redirect is checked before issuing the next GET. 403/429/confirmed challenges stop the family immediately. Cookies, authorization and token values are not persisted.', '',
        'Search titles, URLs, snippets and ItemList/card evidence rank candidates only. Only target-page structured Product identity can establish exact_model or exact_variant. Explicit expected variant fields are all checked, including service index and revision. No production adapter, production orchestrator, extraction of product attributes/media/manuals, dealer fallback, browser automation or registry promotion was added.', '',
        '## Live dry-run', '',
        '| Source | Catalog code | Requests | Queries executed | Candidates | Product probes | Outcome |',
        '| --- | --- | ---: | ---: | ---: | ---: | --- |']
    for run in payload['runs']:
        r = run.get('result', {}); u=r.get('budget_used', {})
        lines.append(f"| {run['source_family']} | {run.get('catalog_identity',{}).get('seller_sku','')} | {u.get('http_requests',0)} | {u.get('search_queries',0)} | {len(r.get('candidates',[]))} | {u.get('product_pages',0)} | {r.get('stop_reason',run.get('stop_reason',''))} |")
    for run in payload['runs']:
        r=run.get('result',{}); cp=r.get('checkpoint',{})
        lines += ['', f"### {run['source_family']}", '']
        for route in cp.get('routes',[]):
            lines.append(f"- Route: `{route['method']} {route['action_url']}`; query key `{route['query_parameter']}`; constants `{json.dumps(route['constant_parameters'],ensure_ascii=False)}`; origin `{route['source']}` from {route['originating_page']}; rejection `{route['rejection_reason'] or 'none'}`.")
        if not cp.get('routes'): lines.append('- No declared search route found.')
        for q in cp.get('queries',[]):
            done=next((x for x in cp.get('completed_queries',[]) if x['query']==q['query']),{})
            lines.append(f"- Query `{q['query']}`: {q['reason']}; outcome `{done.get('outcome','not_executed')}`; final URL `{done.get('final_url','')}`.")
        for candidate in r.get('candidates',[]):
            lines.append(f"- Candidate {candidate['url']}: score {candidate['ranking_score']}; reasons {', '.join(candidate['ranking_reasons'])}; identity `{candidate['identity_verification'].get('level','not_probed')}`; rejection `{candidate['rejection_reason'] or 'none'}`.")
        lines.append(f"- Resume: `{json.dumps(run.get('resume_verification',{}), sort_keys=True)}`.")
        if cp.get('errors'):lines.append(f"- Errors: {cp['errors']}.")
    lines += ['', '## Sitemap versus internal search', '', '| Source | Stage 4 sitemap outcome / requests / candidates | Stage 5 internal search outcome / requests / candidates |', '| --- | --- | --- |']
    for run in payload['runs']:
        previous=sitemap.get(run['source_family'],{}).get('result',{})
        r=run.get('result',{})
        left=f"{previous.get('stop_reason','not sampled')} / {previous.get('budget_used',{}).get('http_requests',0)} / {len(previous.get('candidates',[]))}"
        right=f"{r.get('stop_reason','')} / {r.get('budget_used',{}).get('http_requests',0)} / {len(r.get('candidates',[]))}"
        lines.append(f"| {run['source_family']} | {left} | {right} |")
    lines += ['', 'Stage 4 values are historical, not new network probes. Samples use the same catalog selection rule; LG was not sampled in Stage 4.', '',
        '## Regression and preservation', '',
        f"Protected registry/configuration, LG/Sulpak adapters and Stage 2–4 report hashes unchanged: **{payload['production_registry_unchanged']}**. Full before/after SHA-256 evidence is in dry_run.json. No census labels or queues are rewritten: 186 unresolved_requires_human_review labels, Accesstyle official_source_not_found, next census batch, LG/Sulpak restrictions and the dealer exclusion remain preserved. This is not completion of the all-brand census.", '',
        'Offline regression: see tests.txt for the actual unittest output and count. Fixtures cover unsafe forms, query normalization, dedup/tracking, ranking-only evidence, structured identities, significant variant fields, protection stops, redirect budgets, checkpoints and unchanged registry hashes. Live network is not part of unittest discovery.', '',
        '## One next strategy recommendation', '',
        'Evaluate bounded browser-assisted first-party internal-search discovery for sites whose declared HTML routes are absent or require JavaScript. Retain the same allowlists, query/probe caps, identity gate and immediate protection stop; this recommendation does not authorize bypassing a challenge. Do not implement it in Stage 5.', '']
    (output_dir/'report.md').write_text('\n'.join(lines),encoding='utf-8')


@guarded_entry_point
def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument('--catalog',default=str(ROOT/'data/catalog_2026-09-21_filtered.xlsx'))
    parser.add_argument('--output',default=str(ROOT/'reports/source_census_2026-09-22_stage5'))
    parser.add_argument('--refresh',action='store_true')
    args=parser.parse_args()
    run_stage5_dry_run(args.catalog,args.output,refresh=args.refresh)


if __name__ == '__main__':
    main()
