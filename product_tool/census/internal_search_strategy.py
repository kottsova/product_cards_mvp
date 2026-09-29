"""Bounded internal-search discovery v1. Never changes source readiness/registry."""
from __future__ import annotations
from dataclasses import asdict
import hashlib
import json
import re
import time
from urllib.parse import unquote, urlsplit

from product_tool.identity import ProductIdentity
from .discovery import detect_internal_search, validate_structured_product_identity
from .endpoint_probe import AccessProbe, ProbePolicy
from .models import AccessStatus, EndpointCapability
from .search_routes import SearchHTMLParser, SearchRoute, FLOW, now, safe_url, redact_url
from .sitemap_strategy import (DiscoveryBudget, BudgetUsage, CandidatePage, StrategyResult,
                               normalize_candidate_url, rank_candidate_url)

CHECKPOINT_VERSIONS = {'checkpoint_schema_version': 2, 'strategy_version': '5.1', 'route_detector_version': '2', 'result_parser_version': '3', 'ranking_version': '3'}

SEARCH_OUTCOMES = frozenset({
    'checkpoint_incompatible', 'snapshot_missing',
    'search_route_not_found', 'unsafe_search_route', 'search_javascript_required',
    'search_no_results', 'search_results_found', 'candidate_product_found',
    'exact_model_found', 'exact_variant_found', 'results_identity_insufficient',
    'structured_identity_conflict', 'blocked', 'rate_limited', 'budget_exhausted',
    'deadline_exhausted', 'checkpoint_complete',
})


def generate_search_queries(expected: ProductIdentity):
    """Only model-shaped codes; punctuation carrying identity is preserved."""
    result = []
    def add(value, reason):
        value = ' '.join(str(value or '').split())
        if (not 4 <= len(value) <= 64 or value.casefold() == expected.wb_sku.casefold()
                or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9 ./_-]*', value)
                or not re.search(r'\d', value)
                or not (re.search(r'[A-Za-z]', value) or re.fullmatch(r'\d[\d.-]{5,}', value) and '.' in value)
                or re.search(r'(?i)^\d+\s*(?:GB|TB|MB|CM|MM|INCH)$', value)
                or len(value.split()) > 4):
            return
        if value.casefold() not in {x['query'].casefold() for x in result} and len(result) < 3:
            result.append({'query': value, 'reason': reason})
    add(expected.seller_sku, 'exact_seller_manufacturer_model_code')
    for model in expected.model_candidates:
        if model != expected.seller_sku:
            add(model, 'primary_model_candidate')
            break
    # A valid explicit model may follow a seller code rejected as a marketplace token.
    if not result:
        for model in expected.model_candidates:
            add(model, 'model_candidate')
            if result:
                break
    for item in tuple(result):
        code = item['query']
        compact = re.sub(r'[ -]', '', code)
        add(compact, 'remove_spaces_and_hyphens_preserve_revision_and_index')
        if expected.brand_canonical in {'bosch', 'bosch_home'} and re.search(r'/\d{2}$', code):
            add(code.rsplit('/', 1)[0], 'bosch_enr_without_service_index')
    return tuple(result)


def _exact_token(code, text):
    return bool(re.search(r'(?<![A-Za-z0-9])' + re.escape(code) + r'(?![A-Za-z0-9])', unquote(text), re.I))


from .search_results import parse_search_results


class SearchStop(Exception):
    pass


class InternalSearchStrategy:
    strategy_id = 'internal_search'

    def __init__(self, *, budget=None, probe=None, clock=time.monotonic):
        self.budget = budget or DiscoveryBudget(max_http_requests=10, max_product_candidates=20)
        self.clock = clock
        self.probe = probe or AccessProbe(policy=ProbePolicy(timeout_seconds=10, max_bytes=self.budget.max_response_bytes, min_interval_seconds=self.budget.min_interval_seconds), clock=clock)

    def run(self, *, source_family, source_url, allowed_hosts, expected, configured_endpoints=(), category_hints=(), checkpoint=None, refresh=False, checkpoint_callback=None, configured_product_patterns=(), snapshot_writer=None, snapshot_loader=None, reprocess=False):
        if refresh and reprocess:
            raise ValueError("Choose either snapshot reprocessing or explicit network refresh")
        started = now()
        started_clock = self.clock()
        identity_key = hashlib.sha256(json.dumps({'source': source_family, 'url': source_url, 'hosts': sorted(allowed_hosts), 'identity': expected.to_dict(), 'configured': configured_endpoints}, sort_keys=True).encode()).hexdigest()
        prior = {} if refresh else dict(checkpoint or {})
        if prior and (prior.get('strategy') != self.strategy_id or prior.get('identity_key') != identity_key):
            raise ValueError('Checkpoint belongs to another strategy/source/product/configuration')
        compatibility_key = hashlib.sha256(json.dumps({'versions': CHECKPOINT_VERSIONS, 'identity_key': identity_key, 'category_hints': category_hints, 'configured_product_patterns': configured_product_patterns}, sort_keys=True).encode()).hexdigest()
        compatible = all(prior.get(k) == v for k,v in CHECKPOINT_VERSIONS.items()) and prior.get('compatibility_key') == compatibility_key
        if prior and not compatible and not reprocess:
            return StrategyResult(source_family, (), BudgetUsage(), (), (), ('snapshot_missing',) if not prior.get('snapshots') else (), False, 'checkpoint_incompatible', prior, started, now(), strategy=self.strategy_id, strategy_evidence={'expected_versions': dict(CHECKPOINT_VERSIONS), 'production_ready': False, 'snapshot_status': 'available' if prior.get('snapshots') else 'snapshot_missing'})
        replay_responses = {}
        replay_refs = list(prior.get('snapshots', [])) if reprocess else []
        if reprocess:
            from .search_snapshots import response_from_snapshot
            try:
                if not replay_refs or snapshot_loader is None:
                    raise ValueError('snapshot_missing')
                for ref in replay_refs:
                    stored = snapshot_loader(ref)
                    content_hash = hashlib.sha256(stored['content'].encode('utf-8')).hexdigest()
                    if content_hash != ref['content_sha256'] or content_hash != stored['content_sha256']:
                        raise ValueError('snapshot_hash_mismatch')
                    response = response_from_snapshot(stored, identity_key)
                    replay_responses[(normalize_candidate_url(response.url),response.sample_type)] = response
            except (ValueError, KeyError, OSError) as exc:
                return StrategyResult(source_family, (), BudgetUsage(), (), (), (str(exc),), False, 'snapshot_missing', prior, started, now(), strategy=self.strategy_id, strategy_evidence={'production_ready': False})
            prior = {}  # Rebuild derived data only; never trust old routes/ranks/identities.
        previous_elapsed = float(prior.get('elapsed_seconds', 0))
        deadline = started_clock + max(0.0, self.budget.deadline_seconds - previous_elapsed)
        usage = BudgetUsage(**prior.get('budget_used', {}))
        routes = [SearchRoute.from_dict(x) for x in prior.get('routes', [])]
        candidates = [CandidatePage.from_dict(x) for x in prior.get('candidates', [])]
        queries = list(prior.get('queries', generate_search_queries(expected)))
        completed = list(prior.get('completed_queries', []))
        requests = list(prior.get('requests', []))
        redirects = list(prior.get('redirect_evidence', []))
        events = list(prior.get('events', []))
        probe_results = list(prior.get('probe_results', []))
        snapshots = list(prior.get('snapshots', replay_refs))
        result_audits = list(prior.get('result_audits', []))
        errors = list(prior.get('errors', []))
        route_checked = prior.get('route_checked', False)
        stop = ''
        max_requests = min(10, self.budget.max_http_requests)
        max_candidates = min(20, self.budget.max_product_candidates)
        max_pages = min(3, self.budget.max_product_pages)

        def snapshot(complete=False):
            return {**CHECKPOINT_VERSIONS, 'compatibility_key': compatibility_key, 'processing_mode': 'snapshot_reprocessing' if reprocess else 'network', 'snapshots': snapshots, 'result_audits': result_audits, 'version': 2, 'elapsed_seconds': previous_elapsed + max(0.0, self.clock() - started_clock), 'strategy': self.strategy_id, 'identity_key': identity_key, 'status': 'complete' if complete else 'pending', 'routes': [r.to_dict() for r in routes], 'route_checked': route_checked, 'queries': queries, 'completed_queries': completed, 'requests': requests, 'probe_results': probe_results, 'candidates': [c.to_dict() for c in candidates], 'budget_used': usage.to_dict(), 'redirect_evidence': redirects, 'events': events, 'errors': errors, 'stop_reason': stop, 'started_at': prior.get('started_at', started), 'updated_at': now()}

        def save():
            if checkpoint_callback:
                checkpoint_callback(snapshot())

        def guard(url):
            if self.clock() >= deadline:
                raise SearchStop('deadline_exhausted')
            if usage.http_requests >= max_requests:
                raise SearchStop('budget_exhausted')
            if not safe_url(url, allowed_hosts):
                raise SearchStop('unsafe_search_route')
            usage.http_requests += 1
            requests.append({'url': redact_url(url), 'timestamp': now()})
            return max(0.001, deadline - self.clock())

        def probe(url, capability, sample):
            if reprocess:
                response = replay_responses.get((normalize_candidate_url(url), sample))
                if response is None:
                    errors.append('snapshot_missing:' + redact_url(url))
                    raise SearchStop('snapshot_missing')
            elif isinstance(self.probe, AccessProbe):
                response = self.probe.probe(url, allowed_hosts=allowed_hosts, capability=capability, sample_type=sample, request_guard=guard, deadline=deadline)
            else:
                guard(url)
                response = self.probe.probe(url, allowed_hosts=allowed_hosts, capability=capability, sample_type=sample)
            probe_results.append({'url': redact_url(url), 'final_url': redact_url(response.final_url), 'redirect_chain': [redact_url(x) for x in response.redirect_chain], 'http_status': response.http_status, 'access_status': response.access_status.value, 'protection_status': response.protection_status.value, 'sample_type': sample, 'checked_at': response.checked_at, 'error': response.error})
            chain = (*response.redirect_chain, response.final_url)
            if len(response.redirect_chain) > 1 or response.final_url != url:
                redirects.append({'url': redact_url(url), 'chain': [redact_url(x) for x in response.redirect_chain], 'final_url': redact_url(response.final_url), 'allowed': all(safe_url(x, allowed_hosts) for x in chain)})
            if response.http_status == 429 or response.access_status == AccessStatus.RATE_LIMITED:
                raise SearchStop('rate_limited')
            if response.http_status == 403 or response.access_status == AccessStatus.CAPTCHA_OR_BLOCKED:
                raise SearchStop('blocked')
            if not all(safe_url(x, allowed_hosts) for x in chain):
                raise SearchStop('unsafe_search_route')
            if response.error == 'deadline_exhausted' or self.clock() >= deadline:
                raise SearchStop('deadline_exhausted')
            if snapshot_writer is not None and not reprocess:
                ref = snapshot_writer(response, identity_key)
                if ref is not None:
                    snapshots.append(ref)
            return response

        if prior.get('stop_reason') == 'snapshot_missing':
            stop = 'snapshot_missing'
        elif prior.get('status') == 'complete' or prior.get('stop_reason') in {'blocked', 'rate_limited'} or any(x.get('outcome') in {'blocked', 'rate_limited'} for x in completed):
            stop = 'checkpoint_complete'
        else:
            try:
                if not route_checked:
                    routes = list(detect_internal_search('', source_url, allowed_hosts=allowed_hosts, configured_endpoints=configured_endpoints))
                    if not any(r.executable for r in routes):
                        response = probe(source_url, EndpointCapability.HOMEPAGE, 'search_route_discovery')
                        routes.extend(detect_internal_search(response.diagnostic_text, response.final_url, allowed_hosts=allowed_hosts))
                        route_checked = True
                        if not any(r.executable for r in routes) and response.javascript_required:
                            raise SearchStop('search_javascript_required')
                    route_checked = True
                    save()
                route = next((r for r in routes if r.executable), None)
                if route is None:
                    raise SearchStop('unsafe_search_route' if routes else 'search_route_not_found')
                if not queries:
                    errors.append('no_safe_model_query')
                    raise SearchStop('search_no_results')
                for query in queries[:3]:
                    if any(x['query'] == query['query'] for x in completed):
                        continue
                    if usage.search_queries >= 3:
                        raise SearchStop('budget_exhausted')
                    record = {**query, 'request_url': redact_url(route.query_url(query['query'])), 'timestamp': now(), 'outcome': 'started'}
                    completed.append(record)
                    previous_http = usage.http_requests
                    try:
                        response = probe(route.query_url(query['query']), EndpointCapability.INTERNAL_SEARCH, 'internal_search_query')
                    finally:
                        usage.search_queries += int(reprocess or usage.http_requests > previous_http)
                    record.update(final_url=redact_url(response.final_url), access_status=response.access_status.value)
                    if response.access_status not in {AccessStatus.DIRECT_ACCESS, AccessStatus.JAVASCRIPT_REQUIRED}:
                        record['outcome'] = 'search_no_results'
                        errors.append('search_response_unavailable')
                        save()
                        continue
                    remaining_urls = self.budget.max_urls_read - usage.urls_read
                    if remaining_urls <= 0:
                        raise SearchStop('budget_exhausted')
                    audit = {'response_url': redact_url(response.final_url)}
                    found = parse_search_results(response.diagnostic_text, response_url=response.final_url, expected=expected, source_family=source_family, allowed_hosts=allowed_hosts, category_hints=category_hints, limit=min(max_candidates, remaining_urls), max_bytes=self.budget.max_response_bytes, configured_product_patterns=configured_product_patterns, audit=audit)
                    result_audits.append(audit)
                    merged = {c.url: c for c in candidates}
                    for c in found:
                        if c.url not in merged or c.ranking_score > merged[c.url].ranking_score:
                            merged[c.url] = c
                    candidates = sorted(merged.values(), key=lambda c: (-c.ranking_score, c.url))[:max_candidates]
                    usage.urls_read += len(found)
                    record['outcome'] = 'search_results_found' if found else 'search_no_results'
                    events.append(record['outcome'])
                    save()
                    if not found and response.javascript_required:
                        raise SearchStop('search_javascript_required')
                for candidate in candidates:
                    if candidate.access_status != 'not_checked':
                        continue
                    if usage.product_pages >= max_pages:
                        break
                    previous_http = usage.http_requests
                    try:
                        response = probe(candidate.url, EndpointCapability.PRODUCT_PAGE, 'internal_search_candidate')
                    finally:
                        usage.product_pages += int(reprocess or usage.http_requests > previous_http)
                    candidate.final_url = redact_url(response.final_url)
                    candidate.access_status = response.access_status.value
                    candidate.protection_status = response.protection_status.value
                    if response.access_status in {AccessStatus.DIRECT_ACCESS, AccessStatus.JAVASCRIPT_REQUIRED}:
                        events.append('candidate_product_found')
                        verification = validate_structured_product_identity(response.diagnostic_text, expected=expected, source_url=candidate.final_url)
                        candidate.identity_verification = verification.to_dict()
                        level = verification.level.value
                        candidate.rejection_reason = {'insufficient': 'results_identity_insufficient', 'conflict': 'structured_identity_conflict'}.get(level, '')
                    else:
                        candidate.rejection_reason = 'product_page_unavailable'
                    save()
                    if candidate.identity_verification.get('level') == 'exact_variant' or (candidate.identity_verification.get('level') == 'exact_model' and not expected.variant_attributes.values):
                        break
                levels = {c.identity_verification.get('level') for c in candidates}
                if 'exact_variant' in levels:
                    stop = 'exact_variant_found'
                elif 'exact_model' in levels:
                    stop = 'exact_model_found'
                elif 'conflict' in levels:
                    stop = 'structured_identity_conflict'
                elif candidates:
                    stop = 'results_identity_insufficient'
                else:
                    stop = 'search_no_results'
            except SearchStop as exc:
                stop = str(exc)
                if completed and completed[-1]['outcome'] == 'started':
                    completed[-1]['outcome'] = stop
                if candidates and usage.product_pages and 'candidate' in locals() and candidate.access_status == 'not_checked':
                    candidate.access_status = stop
                    candidate.rejection_reason = stop
        # Final snapshots are immutable replay boundaries. Explicit refresh opts into re-execution.
        cp = snapshot(complete=stop != 'snapshot_missing')
        if stop == 'checkpoint_complete':
            cp = prior
        if checkpoint_callback:
            checkpoint_callback(cp)
        return StrategyResult(source_family, tuple(candidates), usage, (), tuple(redirects), tuple(errors), stop in {'budget_exhausted', 'deadline_exhausted'}, stop, cp, started, now(), strategy=self.strategy_id, strategy_evidence={'routes': cp['routes'], 'queries': cp['queries'], 'completed_queries': cp['completed_queries'], 'events': cp['events'], 'result_audits': result_audits, 'versions': dict(CHECKPOINT_VERSIONS), 'processing_mode': 'snapshot_reprocessing' if reprocess else 'network', 'production_ready': False})


def internal_search_readiness(result):
    levels = {c.identity_verification.get('level') for c in result.candidates}
    return {'product_page_found': any(c.access_status == 'direct_access' for c in result.candidates), 'exact_model_validated': bool(levels & {'exact_model', 'exact_variant'}), 'exact_variant_validated': 'exact_variant' in levels, 'production_ready': False}
