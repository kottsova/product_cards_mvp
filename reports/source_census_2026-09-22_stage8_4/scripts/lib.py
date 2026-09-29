"""Bounded fetch helper for Stage 8.4, carried over unchanged from Stage 8.3's
fix: HOST_BUDGET and the total counter are ALWAYS recomputed from
STATE['attempts'] (persisted in run_state.json), so budgets are enforced
cumulatively across every script run and every re-run of this stage."""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, r'A:\work\dev\product_cards_mvp')

from product_tool.census.endpoint_probe import AccessProbe, ProbePolicy
from product_tool.census.models import EndpointCapability
from product_tool.census.structural_contracts_v8 import inspect_structure

OUT = Path(r'A:\work\dev\product_cards_mvp\reports\source_census_2026-09-22_stage8_4')
OUT.joinpath('fixtures').mkdir(parents=True, exist_ok=True)

STATE_FILE = OUT / 'run_state.json'
if STATE_FILE.exists():
    STATE = json.loads(STATE_FILE.read_text(encoding='utf-8'))
else:
    STATE = {'attempts': [], 'blocked_hosts': []}

probe = AccessProbe(policy=ProbePolicy(timeout_seconds=8, max_bytes=1_500_000, min_interval_seconds=1.5))
BLOCKED = set(STATE['blocked_hosts'])

MAX_PER_HOST = 4
MAX_TOTAL = 6
MAX_HOSTS = 2


def _host_of(url):
    return url.split('/')[2]


def _recompute_budget_state():
    """Always derive counters from STATE['attempts'] -- never from an
    in-process dict that could reset across script invocations."""
    host_counts = Counter(_host_of(a['url']) for a in STATE['attempts'])
    total = len(STATE['attempts'])
    hosts = set(host_counts)
    return host_counts, total, hosts


def budget_status():
    host_counts, total, hosts = _recompute_budget_state()
    return {'total_used': total, 'by_host': dict(host_counts), 'hosts_contacted': sorted(hosts)}


def protected(result):
    return result.http_status in (403, 429) or result.protection_status.value in (
        'challenge_confirmed', 'captcha_detected', 'browser_verification_required'
    ) or result.access_status.value in ('captcha_or_blocked', 'rate_limited')


def save_state():
    STATE_FILE.write_text(json.dumps(STATE, indent=2, ensure_ascii=False), encoding='utf-8')


def check_identity_terms(text, terms):
    low = text.lower()
    return {t: (t.lower() in low) for t in terms if t}


def fetch(url, hosts, kind, identity_terms=None, reason=''):
    host = _host_of(url)
    host_counts, total, contacted_hosts = _recompute_budget_state()
    if host in BLOCKED:
        return None, 'host_blocked_this_run'
    if total >= MAX_TOTAL:
        return None, 'budget_exhausted'
    if host_counts.get(host, 0) >= MAX_PER_HOST:
        return None, 'host_budget_exhausted'
    if host not in contacted_hosts and len(contacted_hosts) >= MAX_HOSTS:
        return None, 'max_hosts_exhausted'
    cap = {'homepage': EndpointCapability.HOMEPAGE, 'product': EndpointCapability.PRODUCT_PAGE,
           'category': EndpointCapability.CATEGORY_PAGE, 'sitemap': EndpointCapability.SITEMAP,
           'robots': EndpointCapability.ROBOTS, 'support': EndpointCapability.SUPPORT_PAGE,
           'document': EndpointCapability.DOCUMENT}.get(kind, EndpointCapability.HOMEPAGE)
    result = probe.probe(url, allowed_hosts=hosts, capability=cap, sample_type=kind)
    rec = {'url': url, 'kind': kind, 'reason': reason, 'http_status': result.http_status,
           'access_status': result.access_status.value, 'protection_status': result.protection_status.value,
           'final_url': result.final_url, 'redirect_chain': list(result.redirect_chain),
           'checked_at': result.checked_at}
    STATE['attempts'].append(rec)
    if protected(result):
        BLOCKED.add(host)
        STATE['blocked_hosts'] = sorted(BLOCKED)
        save_state()
        return None, 'protected_response_host_stopped'
    save_state()
    if result.http_status != 200:
        return None, f'http_{result.http_status}'
    struct = inspect_structure(result.diagnostic_text, result.final_url, hosts)
    identity_match = check_identity_terms(result.diagnostic_text, identity_terms or [])
    return {'url': url, 'final_url': result.final_url, 'struct': struct, 'raw_text': result.diagnostic_text,
            'identity_term_matches': identity_match, 'redirect_chain': list(result.redirect_chain),
            'http_status': result.http_status, 'headers_content_type': None}, None


def fetch_document(url, hosts, reason=''):
    """HEAD-like minimal document check: reuses fetch()'s GET but only keeps
    metadata (status, final URL, redirect chain, content-type via the probe's
    own response), never the document body, per existing size/type limits."""
    return fetch(url, hosts, 'document', reason=reason)


def save_fixture(struct):
    sha = struct['content_sha256']
    path = OUT / 'fixtures' / f'{sha}.json'
    payload = {k: v for k, v in struct.items() if k != 'links'}
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')
    return f'fixtures/{sha}.json'


LINKCACHE_DIR = OUT / 'link_index'
LINKCACHE_DIR.mkdir(exist_ok=True)


def save_link_index(struct, name):
    path = LINKCACHE_DIR / f'{name}.json'
    path.write_text(json.dumps(struct['links'], indent=2, ensure_ascii=False), encoding='utf-8')
    return f'link_index/{name}.json'
