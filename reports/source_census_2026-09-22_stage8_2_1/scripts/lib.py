import json
import sys
from pathlib import Path

sys.path.insert(0, r'A:\work\dev\product_cards_mvp')

from product_tool.census.endpoint_probe import AccessProbe, ProbePolicy
from product_tool.census.models import EndpointCapability
from product_tool.census.structural_contracts_v8 import inspect_structure

OUT = Path(r'A:\work\dev\product_cards_mvp\reports\source_census_2026-09-22_stage8_2_1')
OUT.joinpath('fixtures').mkdir(parents=True, exist_ok=True)

STATE_FILE = OUT / 'run_state.json'
if STATE_FILE.exists():
    STATE = json.loads(STATE_FILE.read_text(encoding='utf-8'))
else:
    STATE = {'attempts': [], 'blocked_hosts': []}

probe = AccessProbe(policy=ProbePolicy(timeout_seconds=8, max_bytes=1_500_000, min_interval_seconds=1.5))
BLOCKED = set(STATE['blocked_hosts'])
HOST_BUDGET = {}
MAX_PER_HOST = 6
MAX_TOTAL = 6  # small, deliberately tight stage budget


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
    host = url.split('/')[2]
    if host in BLOCKED:
        return None, 'host_blocked_this_run'
    if len(STATE['attempts']) >= MAX_TOTAL:
        return None, 'budget_exhausted'
    if HOST_BUDGET.get(host, 0) >= MAX_PER_HOST:
        return None, 'host_budget_exhausted'
    cap = {'homepage': EndpointCapability.HOMEPAGE, 'product': EndpointCapability.PRODUCT_PAGE,
           'category': EndpointCapability.CATEGORY_PAGE, 'sitemap': EndpointCapability.SITEMAP,
           'robots': EndpointCapability.ROBOTS, 'support': EndpointCapability.SUPPORT_PAGE}.get(kind, EndpointCapability.HOMEPAGE)
    result = probe.probe(url, allowed_hosts=hosts, capability=cap, sample_type=kind)
    HOST_BUDGET[host] = HOST_BUDGET.get(host, 0) + 1
    rec = {'url': url, 'kind': kind, 'reason': reason, 'http_status': result.http_status,
           'access_status': result.access_status.value, 'protection_status': result.protection_status.value,
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
    return {'url': url, 'final_url': result.final_url, 'struct': struct, 'raw_len': len(result.diagnostic_text),
            'identity_term_matches': identity_match}, None


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
