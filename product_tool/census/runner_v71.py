"""Stage 7.1 replay first, with optional bounded new title-derived HTTP evidence."""
from dataclasses import replace
from pathlib import Path
from urllib.parse import urlsplit, unquote
import hashlib
import json
import time
from bs4 import BeautifulSoup
from .catalog_identity import VERSION, load_rows, reconcile, as_identity, scope_key, normalized
from .endpoint_probe import guarded_entry_point
from .official_domains import load_domains, routed_domains
from .multi_domain import MultiDomainBudget, best_official, dealer_gate
from .search_snapshots import SearchSnapshotStore
from .search_routes import SearchRoute, safe_url
from .search_results import parse_search_results, path_signals
from .sitemap_strategy import parse_catalog_document, rank_candidate_url
from .structured_identity_v71 import verify_page
from .scoped_access import AccessLedger, AccessObservation

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'reports/source_census_2026-09-22_stage7'
OUTPUT = ROOT / 'reports/source_census_2026-09-22_stage7_1'
WORKBOOK = ROOT / 'data/catalog_2026-09-21_filtered.xlsx'
MAX_NEW_HTTP = 24


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def usable(response):
    return response.get('http_status') == 200 and response.get('access_status') in {'direct_access', 'javascript_required'} and response.get('protection_status') not in {'challenge_detected', 'captcha_detected'}


def read_cache(base=BASE):
    store = object.__new__(SearchSnapshotStore)
    store.path = base / 'source_snapshots.sqlite3'
    cache = read(base / 'supplemental_cache.json')
    for url, item in cache.items():
        item['content'] = store.load(item['snapshot'])['content'] if item.get('snapshot') else ''
    return cache


def search_response_evidence(item, expected, domain):
    """HTTP 200 or a homepage echo is not proof of an executed product search."""
    if not usable(item['response']) or not item.get('content'):
        return False
    soup = BeautifulSoup(item['content'], 'html.parser')
    for node in soup.select('nav,header,footer,aside,[role="navigation"]'):
        node.decompose()
    return bool(parse_search_results(str(soup), response_url=item['response'].get('final_url') or domain.url, expected=expected, source_family=domain.source_family, allowed_hosts=domain.page_hosts + domain.support_hosts, limit=20))


def query_coverage(queries, required, ambiguous=False):
    checked = {normalized(q['query']) for q in queries if q.get('checked')}
    return bool(required) and not ambiguous and set(required) <= checked


def decide(record, domain_results, domains):
    expected = as_identity(record)
    all_domains = bool(domains) and len(domain_results) == len(domains)
    scope_complete = all_domains and all(d['identity_query_scope_complete'] for d in domain_results)
    pending = any(d['unvalidated_candidates'] for d in domain_results)
    best = best_official(domain_results, domains)
    ambiguous = record['review_status'] != 'reconciled'
    if ambiguous:
        outcome = 'identity_review_required'
    elif best and best['identity_verification']['level'] in {'exact_model', 'exact_variant'}:
        outcome = 'official_exact_product_found'
    elif scope_complete and not pending and all(d['search_complete'] for d in domain_results):
        outcome = 'official_exact_product_not_found'
    else:
        outcome = 'official_search_incomplete'
    result = {'outcome': outcome, 'all_official_domains_considered': all_domains, 'identity_query_scope_complete': scope_complete, 'unvalidated_candidates': pending, 'best_official': best}
    result['dealer_fallback'] = dealer_gate(expected, result)
    return result


class BoundedHTTP:
    """The sole network boundary. Redirects consume every aggregate/domain/product cap."""
    def __init__(self, cache, ledger, output, probe=None):
        from .endpoint_probe import AccessProbe, ProbePolicy
        self.probe = probe or AccessProbe(policy=ProbePolicy(timeout_seconds=8, max_bytes=1_000_000, min_interval_seconds=1))
        self.cache, self.ledger, self.output = cache, ledger, output
        self.count = 0
        self.per_domain = {}
        self.per_product = {}
        self.deadlines = {}
        self.receipts = []
        self.store = SearchSnapshotStore(output / 'new_source_snapshots.sqlite3')

    def fetch(self, url, domain, expected, query, *, old_queries, method='internal_search'):
        from .models import EndpointCapability
        if url in self.cache:
            return self.cache[url]
        if query['source_field'] != 'title_raw' or query['confidence'] < .9 or query['query'] in old_queries:
            raise ValueError('new_HTTP_requires_unsearched_high_confidence_real_title_candidate')
        if domain.official_status != 'official_verified':
            raise ValueError('unverified_domain')
        key = (expected.seller_sku, domain.domain_id)
        deadline = self.deadlines.setdefault(key, time.monotonic() + 40)
        hosts = domain.page_hosts + domain.support_hosts
        def guard(target):
            if not safe_url(target, hosts) or self.ledger.paused(target):
                raise RuntimeError('unsafe_or_paused_HTTP_host')
            endpoint = (urlsplit(target).hostname, urlsplit(target).path.rstrip('/'))
            for obs in self.ledger.observations:
                if obs.access_method == 'http' and (obs.host, urlsplit(obs.endpoint).path.rstrip('/')) == endpoint and (obs.http_status in {403, 429} or 'challenge' in obs.protection_status or 'captcha' in obs.protection_status):
                    raise RuntimeError('previously_protected_HTTP_endpoint')
            if self.count >= MAX_NEW_HTTP or self.per_domain.get(key, 0) >= 10 or self.per_product.get(expected.seller_sku, 0) >= 40 or time.monotonic() >= deadline:
                raise RuntimeError('HTTP_budget_or_deadline_exhausted')
            self.count += 1
            self.per_domain[key] = self.per_domain.get(key, 0) + 1
            self.per_product[expected.seller_sku] = self.per_product.get(expected.seller_sku, 0) + 1
            self.receipts.append({'url': target, 'domain_id': domain.domain_id, 'seller_sku': expected.seller_sku, 'query': query['query'], 'method': method, 'access_method': 'http'})
            write(self.output / 'http_attempts.json', self.receipts)
            return max(.001, deadline - time.monotonic())
        response = self.probe.probe(url, allowed_hosts=hosts, capability=EndpointCapability.INTERNAL_SEARCH if method == 'internal_search' else EndpointCapability.PRODUCT_PAGE, sample_type=method, request_guard=guard, deadline=deadline)
        self.ledger.record(response, discovery_method=method, domain_id=domain.domain_id)
        ref = self.store.writer(expected, domain.domain_id)(response, VERSION + ':' + expected.seller_sku)
        item = {'response': response.to_dict(), 'snapshot': ref, 'content': self.store.load(ref)['content'] if ref else '', 'new_title_query': query['query']}
        self.cache[url] = item
        write(self.output / 'new_http_cache.json', {u: {k: v for k, v in r.items() if k != 'content'} for u, r in self.cache.items() if 'new_title_query' in r})
        write(self.output / 'access_observations.json', self.ledger.to_dict())
        return item


def replay_domain(domain, previous, record, cache, *, http=None, old_queries=()):
    expected = as_identity(record)
    ranking_identity = replace(expected, model_candidates=(*expected.model_candidates, *expected.marketing_models))
    hosts = domain.page_hosts + domain.support_hosts
    candidates = {c['url']: dict(c) for c in previous.get('candidates', [])}
    snapshots = {}
    executed = []
    errors = []
    new_links = {}
    def ingest(url, item, origin_query=None):
        if not usable(item['response']) or not item.get('content'):
            return
        if item.get('snapshot'):
            ref = item['snapshot']; snapshots[(ref['store'], ref['snapshot_id'])] = ref
        response_url = item['response'].get('final_url') or url
        if not safe_url(response_url, hosts):
            return
        text = item['content']
        soup = BeautifulSoup('' if item['response'].get('sample_type') == 'sitemap' else text, 'html.parser')
        for node in soup.select('nav,header,footer,aside,[role="navigation"]'):
            node.decompose()
        for found in parse_search_results(str(soup), response_url=response_url, expected=ranking_identity, source_family=domain.source_family, allowed_hosts=hosts, limit=20):
            if path_signals(found.url)[1]:
                continue
            candidates[found.url] = found.to_dict()
            if origin_query:
                new_links[found.url] = origin_query
        if item['response'].get('sample_type') == 'sitemap':
            try:
                kind, locations, truncated = parse_catalog_document(text, max_urls=800)
            except ValueError:
                return
            if kind == 'urlset':
                for location in locations:
                    score, reasons, cats, models = rank_candidate_url(location, expected=ranking_identity, source_family=domain.source_family, allowed_hosts=hosts)
                    if models and safe_url(location, hosts) and not path_signals(location)[1]:
                        candidates.setdefault(location, {'url': location, 'ranking_score': score, 'ranking_reasons': list(reasons), 'strategy': 'offline_sitemap'})
    # Replay only evidence already routed to this official domain, including search/sitemaps.
    urls = {r['requested_url'] for r in previous.get('requests', [])}
    urls.update(c['url'] for c in previous.get('candidates', []))
    for url in sorted(urls):
        if url in cache:
            ingest(url, cache[url])
    routes = [SearchRoute.from_dict(r) for r in previous.get('routes', [])]
    route = next((r for r in routes if r.executable and safe_url(r.action_url, hosts)), None)
    for query in record['queries']:
        checked = False
        response_received = False
        origin = 'not_executed'
        url = route.query_url(query['query']) if route else None
        # Retain the exact historical request URL when query case differs only by normalization.
        old = next((r['requested_url'] for r in previous.get('requests', []) if r.get('discovery_method') == 'internal_search' and any(normalized(value) == query['query'] for _, value in __import__('urllib.parse', fromlist=['parse_qsl']).parse_qsl(urlsplit(r['requested_url']).query))), None)
        if old in cache:
            url = old
        if url in cache:
            ingest(url, cache[url]); response_received = usable(cache[url]['response']); checked = search_response_evidence(cache[url], ranking_identity, domain); origin = 'stage7_1_snapshot_replay' if 'new_title_query' in cache[url] else 'snapshot_replay'
        elif http and url and record['review_status'] == 'reconciled' and query['source_field'] == 'title_raw' and query['confidence'] >= .9 and query['query'] not in old_queries:
            try:
                item = http.fetch(url, domain, expected, query, old_queries=old_queries)
                ingest(url, item, query); response_received = usable(item['response']); checked = search_response_evidence(item, ranking_identity, domain); origin = 'new_http'
            except (RuntimeError, ValueError) as exc:
                errors.append(str(exc)); origin = 'stopped'
        executed.append(dict(query, checked=checked, response_received=response_received, origin=origin, url=url))
    # Rerank before bounded target validation. A URL token is discovery evidence only.
    for url, candidate in candidates.items():
        score, reasons, _, _ = rank_candidate_url(url, expected=ranking_identity, source_family=domain.source_family, allowed_hosts=hosts)
        candidate['ranking_score'] = score
        candidate['ranking_reasons'] = list(reasons)
    ordered = sorted(candidates.values(), key=lambda c: (-c['ranking_score'], c['url']))
    new_targets = 0
    for candidate in ordered:
        url = candidate['url']
        item = cache.get(url) or next((v for v in cache.values() if v['response'].get('final_url') == url), None)
        if not item and http and url in new_links and new_targets < 3:
            new_targets += 1
            try:
                item = http.fetch(url, domain, expected, new_links[url], old_queries=old_queries, method='product')
            except (RuntimeError, ValueError) as exc:
                errors.append(str(exc))
        if item and usable(item['response']) and safe_url(item['response'].get('final_url') or url, hosts) and item.get('content'):
            candidate['identity_verification'] = verify_page(item['content'], expected, domain)
            candidate['validation_origin'] = 'new_http' if 'new_title_query' in item else 'snapshot_replay'
            if item.get('snapshot'):
                ref = item['snapshot']; snapshots[(ref['store'], ref['snapshot_id'])] = ref
        else:
            candidate['identity_verification'] = {'level': 'unvalidated', 'reason': 'missing_or_unusable_snapshot', 'evidence': []}
    complete = query_coverage(executed, record['high_confidence_candidates'], record['review_status'] != 'reconciled')
    pending = any(c['identity_verification']['level'] == 'unvalidated' for c in ordered)
    return {'domain_id': domain.domain_id, 'queries': executed, 'identity_query_scope_complete': complete, 'snapshots_reused': list(snapshots.values()), 'candidates': ordered, 'unvalidated_candidates': pending, 'search_complete': complete and not pending and not previous.get('truncated', True) and previous.get('outcome') == 'bounded_discovery_complete' and not errors, 'baseline_truncated': previous.get('truncated'), 'errors': errors, 'browser_used': False}


def execute(*, live=False, replay_saved=False):
    OUTPUT.mkdir(exist_ok=True)
    final_path = OUTPUT / 'final_results.json'
    if live and replay_saved:
        raise ValueError('saved replay is strictly offline')
    if final_path.exists() and not replay_saved:
        raise RuntimeError('Stage 7.1 result exists: inspect checkpoint; do not silently repeat HTTP')
    baseline = read(BASE / 'final_results.json')
    raw_rows = load_rows(WORKBOOK, [r['identity']['seller_sku'] for r in baseline['runs']])
    workbook_hash = hashlib.sha256(WORKBOOK.read_bytes()).hexdigest()
    domains = load_domains()
    cache = read_cache()
    records = {sku: reconcile(rows) for sku, rows in raw_rows.items()}
    def run_all(http=None):
        runs = []
        for old in baseline['runs']:
            record = records[old['identity']['seller_sku']]
            expected = as_identity(record)
            selected = routed_domains(domains, expected, old['source_family'], research=True)
            previous = {d['domain_id']: d for d in old['domains']}
            searched = {normalized(q) for d in old['domains'] for q in d.get('queries', [])}
            results = [replay_domain(d, previous.get(d.domain_id, {}), record, cache, http=http, old_queries=searched) for d in selected]
            result = {'version': VERSION, 'source_family': old['source_family'], 'catalog_identity': record, 'scope': scope_key(record, [d.to_dict() for d in selected], workbook_hash), 'baseline_scope': old['scope'], 'old_checkpoint_status': 'checkpoint_incompatible', 'before': old['outcome'], 'domains': results, 'http_requests': http.per_product.get(expected.seller_sku, 0) if http else 0}
            result.update(decide(record, results, selected)); runs.append(result)
        return {'version': VERSION, 'runs': runs, 'new_http_requests': http.count if http else 0, 'chromium_launches': 0, 'workbook_sha256': workbook_hash, 'aggregate_new_HTTP_cap': MAX_NEW_HTTP, 'budget': {**__import__('dataclasses').asdict(MultiDomainBudget()), 'max_queries': 3}, 'production_ready': False}
    offline = run_all()
    write(OUTPUT / 'offline_results.json', offline)
    final = offline
    if replay_saved and (OUTPUT / 'new_http_cache.json').exists():
        store = object.__new__(SearchSnapshotStore)
        store.path = OUTPUT / 'new_source_snapshots.sqlite3'
        for url, item in read(OUTPUT / 'new_http_cache.json').items():
            item['content'] = store.load(item['snapshot'])['content'] if item.get('snapshot') else ''
            cache[url] = item
        final = run_all()
    if live:
        if (OUTPUT / 'http_attempts.json').exists():
            raise RuntimeError('Existing HTTP attempts require offline recovery')
        saved = read(BASE / 'supplemental_access.json')
        ledger = AccessLedger([AccessObservation(**x) for x in saved['observations']])
        ledger.paused_hosts = {(x['host'], x['access_method']): AccessObservation(**x) for x in saved['run_host_pauses']}
        final = run_all(BoundedHTTP(cache, ledger, OUTPUT))
    if replay_saved:
        attempts = read(OUTPUT / 'http_attempts.json') if (OUTPUT / 'http_attempts.json').exists() else []
        final['new_http_requests'] = len(attempts)
        final['replay_http_requests'] = 0
        for result in final['runs']:
            result['http_requests'] = sum(a['seller_sku'] == result['catalog_identity']['seller_sku_raw'] for a in attempts)
    write(final_path, final)
    return final

@guarded_entry_point
def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--replay-saved', action='store_true')
    args = parser.parse_args()
    result = execute(live=args.live, replay_saved=args.replay_saved)
    print(json.dumps({'new_http_requests': result['new_http_requests'], 'outcomes': {r['catalog_identity']['seller_sku_raw']: r['outcome'] for r in result['runs']}}, ensure_ascii=True))


if __name__ == '__main__':
    main()
