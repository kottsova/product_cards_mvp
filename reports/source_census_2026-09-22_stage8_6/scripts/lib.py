"""Bounded fetch helper for Stage 8.6. Carries over Stage 8.3-8.5's fixed
counter-persistence logic unchanged (budgets recomputed from run_state.json
on every call, never from an in-process value).

Adds a bounded, Range-aware document-assembly capability
(fetch_document_bounded) as a REUSABLE pipeline piece for large official
instructions, tested here against Samsung's MS23K3614AK/BW manual PDF.

Size-check fix (per this stage's instructions): every completeness check in
this module counts raw response bytes only. Nothing here ever measures a
UTF-8-decoded text string's length as a proxy for byte count (that was
Stage 8.4's bug; Stage 8.5's fetch_binary already avoided it; this module
keeps the same discipline and adds an explicit, testable classification of
full / partial / unknown-completeness responses).

The existing ordinary page-load cap (1,500,000 bytes, ProbePolicy.max_bytes)
is NOT changed here and is still used, unmodified, for HTML page fetches via
fetch(). The document capability below uses that same number only as its
per-request chunk size when Range is supported -- never as a claim that a
document under that size is "complete" without checking Content-Range/
Content-Length.
"""
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, r'A:\work\dev\product_cards_mvp')

from product_tool.census.endpoint_probe import AccessProbe, ProbePolicy
from product_tool.census.models import EndpointCapability
from product_tool.census.structural_contracts_v8 import inspect_structure

OUT = Path(r'A:\work\dev\product_cards_mvp\reports\source_census_2026-09-22_stage8_6')
OUT.joinpath('fixtures').mkdir(parents=True, exist_ok=True)

STATE_FILE = OUT / 'run_state.json'
if STATE_FILE.exists():
    STATE = json.loads(STATE_FILE.read_text(encoding='utf-8'))
else:
    STATE = {'attempts': [], 'rejected_attempts': [], 'blocked_hosts': []}
STATE.setdefault('rejected_attempts', [])

# --- Budget, fixed BEFORE the first network call of this stage -------------
ORDINARY_PAGE_MAX_BYTES = 1_500_000  # unchanged existing limit, used for HTML page fetch() only
DOCUMENT_CHUNK_BYTES = 1_500_000     # per-request Range chunk size, reuses the same existing number
# Revised per budget_revision.json (declared before any request made under the new values):
# the control document's confirmed size (10,572,005 bytes, via Content-Range) exceeded the
# original 6,000,000-byte cap. Raised to a still-fixed, still-finite ceiling comfortably above
# the confirmed total -- not an unbounded/adaptive limit.
MAX_DOCUMENT_TOTAL_BYTES = 12_000_000
MAX_PER_HOST = 10
MAX_TOTAL = 12
MAX_HOSTS = 2
ALLOWED_STAGE_HOSTS = {'org.downloadcenter.samsung.com', 'downloadcenter.samsung.com'}

POLICY = ProbePolicy(timeout_seconds=8, max_bytes=ORDINARY_PAGE_MAX_BYTES, min_interval_seconds=1.5)
probe = AccessProbe(policy=POLICY)
BLOCKED = set(STATE['blocked_hosts'])


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


def _protected(http_status):
    return http_status in (403, 429)


_last_request_at = {'t': None}


def _respect_rate_limit():
    last = _last_request_at['t']
    if last is not None:
        remaining = POLICY.min_interval_seconds - (time.monotonic() - last)
        if remaining > 0:
            time.sleep(remaining)


CONTENT_RANGE_RE = re.compile(r'bytes\s+(\d+)-(\d+)/(\d+)')


def _single_range_request(url, hosts, range_start, range_end, reason):
    """One bounded GET with a Range header. Returns a dict with status,
    headers of interest, and raw bytes actually read (capped defensively at
    DOCUMENT_CHUNK_BYTES regardless of what the server claims), or (None, err).
    Every call, successful or not, is logged as one counted attempt."""
    gate = _budget_gate(url, 'document_range', reason)
    if gate:
        return None, gate
    _respect_rate_limit()
    session = probe.session
    headers = {'User-Agent': POLICY.user_agent, 'Accept': 'application/pdf,*/*;q=0.1',
               'Range': f'bytes={range_start}-{range_end}'}
    try:
        resp = session.get(url, timeout=POLICY.timeout_seconds, headers=headers, allow_redirects=True, stream=True)
    except Exception as exc:
        rec = {'url': url, 'kind': 'document_range', 'reason': reason, 'http_status': None,
               'range_requested': f'{range_start}-{range_end}', 'error': str(exc), 'checked_at': None}
        STATE['attempts'].append(rec)
        save_state()
        return None, 'network_error'
    _last_request_at['t'] = time.monotonic()

    redirect_chain = [r.url for r in resp.history] + [resp.url]
    for target in redirect_chain:
        target_host = urlsplit(target).hostname or ''
        if target_host not in hosts:
            resp.close()
            rec = {'url': url, 'kind': 'document_range', 'reason': reason, 'http_status': resp.status_code,
                   'range_requested': f'{range_start}-{range_end}', 'final_url': resp.url,
                   'redirect_chain': redirect_chain, 'rejected': f'unapproved_redirect_host:{target_host}', 'checked_at': None}
            STATE['attempts'].append(rec)
            save_state()
            return None, f'unapproved_redirect_host:{target_host}'

    if _protected(resp.status_code):
        BLOCKED.add(_host_of(url))
        STATE['blocked_hosts'] = sorted(BLOCKED)
        rec = {'url': url, 'kind': 'document_range', 'reason': reason, 'http_status': resp.status_code,
               'range_requested': f'{range_start}-{range_end}', 'final_url': resp.url,
               'redirect_chain': redirect_chain, 'checked_at': None}
        STATE['attempts'].append(rec)
        save_state()
        resp.close()
        return None, 'protected_response_host_stopped'

    chunks = []
    size = 0
    cap = DOCUMENT_CHUNK_BYTES + 1024  # small slack for off-by-one range math, still strictly bounded
    for chunk in resp.iter_content(chunk_size=32_768):
        if not chunk:
            continue
        remaining = cap - size
        if remaining <= 0:
            break
        chunks.append(chunk[:remaining])
        size += min(len(chunk), remaining)
        if size >= cap:
            break
    resp.close()
    data = b''.join(chunks)

    content_range = resp.headers.get('Content-Range', '')
    content_length_header = resp.headers.get('Content-Length')
    etag = resp.headers.get('ETag')
    last_modified = resp.headers.get('Last-Modified')
    accept_ranges = resp.headers.get('Accept-Ranges')

    rec = {
        'url': url, 'kind': 'document_range', 'reason': reason, 'http_status': resp.status_code,
        'range_requested': f'{range_start}-{range_end}', 'final_url': resp.url, 'redirect_chain': redirect_chain,
        'content_range_header': content_range, 'content_length_header': content_length_header,
        'accept_ranges_header': accept_ranges, 'etag': etag, 'last_modified': last_modified,
        'bytes_read': len(data), 'checked_at': None,
    }
    STATE['attempts'].append(rec)
    save_state()

    return {
        'status_code': resp.status_code, 'bytes': data, 'content_range': content_range,
        'content_length_header': content_length_header, 'etag': etag, 'last_modified': last_modified,
        'accept_ranges': accept_ranges, 'final_url': resp.url,
    }, None


def fetch_document_bounded(url, hosts, reason=''):
    """Bounded, Range-aware document fetch. Returns a result dict describing
    exactly what was obtained and its completeness classification -- one of
    'complete', 'partial', 'unknown_completeness' -- never silently assumes
    completeness. Uses raw byte counts throughout, never decoded-text length.
    """
    log = {'steps': []}

    first, err = _single_range_request(url, hosts, 0, DOCUMENT_CHUNK_BYTES - 1, reason + ' [probe: first chunk via Range]')
    if first is None:
        log['steps'].append({'step': 'probe', 'result': 'failed', 'error': err})
        return {'completeness': 'unknown_completeness', 'bytes': None, 'reason': f'probe_failed:{err}', 'log': log}
    log['steps'].append({'step': 'probe', 'status_code': first['status_code'], 'content_range': first['content_range'],
                          'accept_ranges': first['accept_ranges'], 'bytes_read': len(first['bytes'])})

    m = CONTENT_RANGE_RE.match(first['content_range'] or '')
    if first['status_code'] == 206 and m:
        start, end, total = int(m.group(1)), int(m.group(2)), int(m.group(3))
        log['range_supported'] = True
        log['declared_total_bytes'] = total
        if total > MAX_DOCUMENT_TOTAL_BYTES:
            log['steps'].append({'step': 'size_check', 'result': 'exceeds_declared_max', 'total': total, 'cap': MAX_DOCUMENT_TOTAL_BYTES})
            return {'completeness': 'unknown_completeness', 'bytes': None,
                    'reason': f'total_size_{total}_exceeds_declared_cap_{MAX_DOCUMENT_TOTAL_BYTES}_bytes_not_fetched_further',
                    'log': log, 'declared_total_bytes': total}
        parts = [(start, end, first['bytes'])]
        reference_etag = first['etag']
        reference_last_modified = first['last_modified']
        next_start = end + 1
        while next_start < total:
            next_end = min(next_start + DOCUMENT_CHUNK_BYTES - 1, total - 1)
            part, perr = _single_range_request(url, hosts, next_start, next_end, reason + f' [assembly chunk {next_start}-{next_end}]')
            if part is None:
                log['steps'].append({'step': 'assembly_chunk', 'range': f'{next_start}-{next_end}', 'result': 'failed', 'error': perr})
                return {'completeness': 'partial', 'bytes': b''.join(p[2] for p in parts),
                        'reason': f'assembly_stopped_early:{perr}', 'log': log, 'declared_total_bytes': total,
                        'bytes_assembled': sum(len(p[2]) for p in parts)}
            pm = CONTENT_RANGE_RE.match(part['content_range'] or '')
            if part['status_code'] != 206 or not pm:
                log['steps'].append({'step': 'assembly_chunk', 'range': f'{next_start}-{next_end}', 'result': 'server_stopped_honoring_range'})
                return {'completeness': 'partial', 'bytes': b''.join(p[2] for p in parts),
                        'reason': 'server_stopped_returning_206_mid_assembly', 'log': log, 'declared_total_bytes': total,
                        'bytes_assembled': sum(len(p[2]) for p in parts)}
            p_start, p_end, p_total = int(pm.group(1)), int(pm.group(2)), int(pm.group(3))
            if p_total != total:
                log['steps'].append({'step': 'assembly_chunk', 'range': f'{next_start}-{next_end}', 'result': 'total_size_mismatch',
                                      'expected_total': total, 'got_total': p_total})
                return {'completeness': 'unknown_completeness', 'bytes': None,
                        'reason': 'aborted_total_size_changed_between_parts_possible_different_document_version',
                        'log': log, 'declared_total_bytes': total}
            if reference_etag and part['etag'] and part['etag'] != reference_etag:
                log['steps'].append({'step': 'assembly_chunk', 'range': f'{next_start}-{next_end}', 'result': 'etag_mismatch',
                                      'expected_etag': reference_etag, 'got_etag': part['etag']})
                return {'completeness': 'unknown_completeness', 'bytes': None,
                        'reason': 'aborted_etag_changed_between_parts_would_splice_different_document_versions',
                        'log': log, 'declared_total_bytes': total}
            if reference_last_modified and part['last_modified'] and part['last_modified'] != reference_last_modified:
                log['steps'].append({'step': 'assembly_chunk', 'range': f'{next_start}-{next_end}', 'result': 'last_modified_mismatch',
                                      'expected': reference_last_modified, 'got': part['last_modified']})
                return {'completeness': 'unknown_completeness', 'bytes': None,
                        'reason': 'aborted_last_modified_changed_between_parts_would_splice_different_document_versions',
                        'log': log, 'declared_total_bytes': total}
            log['steps'].append({'step': 'assembly_chunk', 'range': f'{p_start}-{p_end}', 'result': 'ok', 'bytes_read': len(part['bytes'])})
            parts.append((p_start, p_end, part['bytes']))
            next_start = p_end + 1
        assembled = b''.join(p[2] for p in sorted(parts, key=lambda x: x[0]))
        complete = len(assembled) == total
        return {'completeness': 'complete' if complete else 'partial', 'bytes': assembled,
                'reason': 'assembled_from_range_parts_size_matches_declared_total' if complete else 'assembled_size_does_not_match_declared_total',
                'log': log, 'declared_total_bytes': total, 'bytes_assembled': len(assembled)}

    # Range not honored (status 200 or something else) -- do not attempt an unbounded download.
    log['range_supported'] = False
    content_length = first['content_length_header']
    if first['status_code'] == 200 and content_length and content_length.isdigit():
        total = int(content_length)
        if total > MAX_DOCUMENT_TOTAL_BYTES:
            log['steps'].append({'step': 'size_check', 'result': 'exceeds_declared_max_no_range_support', 'total': total})
            return {'completeness': 'unknown_completeness', 'bytes': None,
                    'reason': f'range_unsupported_and_content_length_{total}_exceeds_cap_{MAX_DOCUMENT_TOTAL_BYTES}_not_fetched_further',
                    'log': log, 'declared_total_bytes': total}
        if len(first['bytes']) == total:
            return {'completeness': 'complete', 'bytes': first['bytes'],
                    'reason': 'range_unsupported_but_content_length_matched_bytes_read_in_a_single_bounded_response', 'log': log,
                    'declared_total_bytes': total, 'bytes_assembled': len(first['bytes'])}
        return {'completeness': 'partial', 'bytes': first['bytes'],
                'reason': f'range_unsupported_content_length_{total}_but_only_{len(first["bytes"])}_bytes_read_within_one_bounded_request',
                'log': log, 'declared_total_bytes': total, 'bytes_assembled': len(first['bytes'])}
    return {'completeness': 'unknown_completeness', 'bytes': first['bytes'],
            'reason': 'range_unsupported_and_no_usable_content_length_header_true_total_size_unknown',
            'log': log, 'bytes_assembled': len(first['bytes'])}
