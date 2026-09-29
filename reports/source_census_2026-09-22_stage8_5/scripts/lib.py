"""Bounded fetch helper for Stage 8.5. Carries over Stage 8.3/8.4's fixed
counter-persistence logic unchanged (budgets recomputed from run_state.json
on every call, never from an in-process value).

Adds one new capability: fetch_binary(), a minimal binary-safe fetch path
for the PDF document check. AccessProbe.probe() decodes every response as
text via `bytes.decode(encoding, errors='replace')` before returning it
(product_tool/census/endpoint_probe.py) -- for a PDF's binary content this
is a lossy, one-way transform (invalid byte sequences become U+FFFD and
cannot be recovered), so pypdf cannot reliably parse anything read back
through probe.probe(). fetch_binary() reuses the SAME requests.Session,
ProbePolicy timeout/max_bytes/user-agent values, and the same redirect-host
safety check and 403/429 handling as AccessProbe, just without the
text-decode step -- it is a scoped extension for this one binary-content
case, not a new fetch pipeline.
"""
import json
import sys
import time
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, r'A:\work\dev\product_cards_mvp')

from product_tool.census.endpoint_probe import AccessProbe, ProbePolicy
from product_tool.census.models import EndpointCapability
from product_tool.census.structural_contracts_v8 import inspect_structure

OUT = Path(r'A:\work\dev\product_cards_mvp\reports\source_census_2026-09-22_stage8_5')
OUT.joinpath('fixtures').mkdir(parents=True, exist_ok=True)

STATE_FILE = OUT / 'run_state.json'
if STATE_FILE.exists():
    STATE = json.loads(STATE_FILE.read_text(encoding='utf-8'))
else:
    STATE = {'attempts': [], 'rejected_attempts': [], 'blocked_hosts': []}
STATE.setdefault('rejected_attempts', [])

POLICY = ProbePolicy(timeout_seconds=8, max_bytes=1_500_000, min_interval_seconds=1.5)
probe = AccessProbe(policy=POLICY)
BLOCKED = set(STATE['blocked_hosts'])

# Budget fixed BEFORE the first network call of this stage, including the
# Samsung document-serving domains observed in Stage 8.4's redirect chain.
MAX_PER_HOST = 3
MAX_TOTAL = 5
MAX_HOSTS = 3
ALLOWED_STAGE_HOSTS = {'www.samsung.com', 'org.downloadcenter.samsung.com', 'downloadcenter.samsung.com', 'images.samsung.com'}


def _host_of(url):
    return urlsplit(url).hostname or ''


def _recompute_budget_state():
    host_counts = Counter(_host_of(a['url']) for a in STATE['attempts'])
    total = len(STATE['attempts'])
    hosts = set(host_counts)
    return host_counts, total, hosts


def budget_status():
    host_counts, total, hosts = _recompute_budget_state()
    return {'total_used': total, 'by_host': dict(host_counts), 'hosts_contacted': sorted(hosts)}


def protected(http_status, protection_status=None, access_status=None):
    if http_status in (403, 429):
        return True
    if protection_status in ('challenge_confirmed', 'captcha_detected', 'browser_verification_required'):
        return True
    if access_status in ('captcha_or_blocked', 'rate_limited'):
        return True
    return False


def save_state():
    STATE_FILE.write_text(json.dumps(STATE, indent=2, ensure_ascii=False), encoding='utf-8')


def _record_rejected(url, kind, reason, why):
    STATE['rejected_attempts'].append({'url': url, 'kind': kind, 'reason': reason, 'why_rejected': why})
    save_state()


def _budget_gate(url, kind, reason):
    host = _host_of(url)
    if host not in ALLOWED_STAGE_HOSTS:
        _record_rejected(url, kind, reason, 'host_not_in_pre_declared_allowlist')
        return 'host_not_pre_declared'
    host_counts, total, contacted_hosts = _recompute_budget_state()
    if host in BLOCKED:
        _record_rejected(url, kind, reason, 'host_blocked_this_run')
        return 'host_blocked_this_run'
    if total >= MAX_TOTAL:
        _record_rejected(url, kind, reason, 'total_budget_exhausted')
        return 'budget_exhausted'
    if host_counts.get(host, 0) >= MAX_PER_HOST:
        _record_rejected(url, kind, reason, 'per_host_budget_exhausted')
        return 'host_budget_exhausted'
    if host not in contacted_hosts and len(contacted_hosts) >= MAX_HOSTS:
        _record_rejected(url, kind, reason, 'max_hosts_exhausted')
        return 'max_hosts_exhausted'
    return None


def check_identity_terms(text, terms):
    low = text.lower()
    return {t: (t.lower() in low) for t in terms if t}


def fetch(url, hosts, kind, identity_terms=None, reason=''):
    gate = _budget_gate(url, kind, reason)
    if gate:
        return None, gate
    cap = {'homepage': EndpointCapability.HOMEPAGE, 'product': EndpointCapability.PRODUCT_PAGE,
           'category': EndpointCapability.CATEGORY_PAGE, 'sitemap': EndpointCapability.SITEMAP,
           'robots': EndpointCapability.ROBOTS, 'support': EndpointCapability.SUPPORT_PAGE,
           'document': EndpointCapability.DOCUMENT}.get(kind, EndpointCapability.HOMEPAGE)
    result = probe.probe(url, allowed_hosts=hosts, capability=cap, sample_type=kind)
    host = _host_of(url)
    rec = {'url': url, 'kind': kind, 'reason': reason, 'http_status': result.http_status,
           'access_status': result.access_status.value, 'protection_status': result.protection_status.value,
           'final_url': result.final_url, 'redirect_chain': list(result.redirect_chain),
           'checked_at': result.checked_at}
    STATE['attempts'].append(rec)
    if protected(result.http_status, result.protection_status.value, result.access_status.value):
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
            'http_status': result.http_status}, None


_last_binary_request_at = {'t': None}


def fetch_binary(url, hosts, reason=''):
    """Binary-safe GET for document content (e.g. PDF). Reuses probe.session,
    POLICY.timeout_seconds/max_bytes/user_agent and the same redirect-host
    safety + 403/429 handling as AccessProbe.probe(), but returns raw bytes
    instead of a lossily-decoded string. Counts against the same budget."""
    gate = _budget_gate(url, 'document_binary', reason)
    if gate:
        return None, gate
    host = _host_of(url)
    # Respect the same minimum request interval as AccessProbe.
    last = _last_binary_request_at['t']
    if last is not None:
        remaining = POLICY.min_interval_seconds - (time.monotonic() - last)
        if remaining > 0:
            time.sleep(remaining)
    session = probe.session
    try:
        resp = session.get(url, timeout=POLICY.timeout_seconds,
                            headers={'User-Agent': POLICY.user_agent, 'Accept': 'application/pdf,*/*;q=0.1'},
                            allow_redirects=True, stream=True)
    except Exception as exc:  # network failure -- not a content result
        rec = {'url': url, 'kind': 'document_binary', 'reason': reason, 'http_status': None,
               'access_status': 'unavailable', 'protection_status': 'inconclusive',
               'final_url': None, 'redirect_chain': [], 'checked_at': None, 'error': str(exc)}
        STATE['attempts'].append(rec)
        save_state()
        return None, 'network_error'
    _last_binary_request_at['t'] = time.monotonic()
    redirect_chain = [r.url for r in resp.history] + [resp.url]
    for target in redirect_chain:
        target_host = urlsplit(target).hostname or ''
        if target_host not in hosts:
            resp.close()
            rec = {'url': url, 'kind': 'document_binary', 'reason': reason, 'http_status': resp.status_code,
                   'access_status': 'regional_redirect', 'protection_status': 'inconclusive',
                   'final_url': resp.url, 'redirect_chain': redirect_chain, 'checked_at': None}
            STATE['attempts'].append(rec)
            save_state()
            return None, f'unapproved_redirect_host:{target_host}'
    content_type = resp.headers.get('content-type', '')
    if resp.status_code in (403, 429):
        BLOCKED.add(host)
        STATE['blocked_hosts'] = sorted(BLOCKED)
        rec = {'url': url, 'kind': 'document_binary', 'reason': reason, 'http_status': resp.status_code,
               'access_status': 'captcha_or_blocked', 'protection_status': 'challenge_confirmed',
               'final_url': resp.url, 'redirect_chain': redirect_chain, 'checked_at': None}
        STATE['attempts'].append(rec)
        save_state()
        resp.close()
        return None, 'protected_response_host_stopped'
    chunks = []
    size = 0
    for chunk in resp.iter_content(chunk_size=32_768):
        if not chunk:
            continue
        remaining = POLICY.max_bytes - size
        if remaining <= 0:
            break
        chunks.append(chunk[:remaining])
        size += min(len(chunk), remaining)
        if size >= POLICY.max_bytes:
            break
    resp.close()
    rec = {'url': url, 'kind': 'document_binary', 'reason': reason, 'http_status': resp.status_code,
           'access_status': 'direct_access' if resp.status_code == 200 else 'unavailable',
           'protection_status': 'ordinary_page', 'final_url': resp.url, 'redirect_chain': redirect_chain,
           'checked_at': None, 'bytes_read': size, 'content_type': content_type,
           'truncated': size >= POLICY.max_bytes}
    STATE['attempts'].append(rec)
    save_state()
    if resp.status_code != 200:
        return None, f'http_{resp.status_code}'
    data = b''.join(chunks)
    return {'bytes': data, 'final_url': resp.url, 'content_type': content_type,
            'bytes_read': size, 'truncated': size >= POLICY.max_bytes}, None


def save_fixture(struct):
    sha = struct['content_sha256']
    path = OUT / 'fixtures' / f'{sha}.json'
    payload = {k: v for k, v in struct.items() if k != 'links'}
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')
    return f'fixtures/{sha}.json'
