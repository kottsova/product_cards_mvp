import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, r'A:\work\dev\product_cards_mvp')

from product_tool.census.endpoint_probe import AccessProbe, ProbePolicy
from product_tool.census.models import EndpointCapability  # noqa: F401

ROOT = Path(r'A:\work\dev\product_cards_mvp')
OUT = ROOT / 'reports/source_census_2026-09-23_stage11_1'


def load_budget():
    return json.loads((OUT / 'budget_predeclaration.json').read_text(encoding='utf-8'))


def make_probe(budget, *, max_bytes_key='max_response_bytes_per_request_pages'):
    limits = budget['limits']
    policy = ProbePolicy(
        timeout_seconds=limits['timeout_seconds_per_request'],
        max_bytes=limits[max_bytes_key],
        min_interval_seconds=limits['min_interval_seconds_between_requests'],
    )
    return AccessProbe(policy=policy)


class RequestLogger:
    def __init__(self):
        self.entries = []
        self.rejected = []

    def record(self, url, capability, result, note=''):
        entry = {
            'seq': len(self.entries) + 1,
            'requested_url': url,
            'capability': capability.value if hasattr(capability, 'value') else str(capability),
            'access_status': result.access_status.value,
            'http_status': result.http_status,
            'final_url': result.final_url,
            'redirect_chain': list(result.redirect_chain),
            'content_type': result.content_type,
            'protection_status': result.protection_status.value,
            'error': result.error,
            'bytes_read': next((e.get('bytes_read') for e in result.evidence if e.get('type') == 'bounded_get'), 0),
            'note': note,
        }
        self.entries.append(entry)
        return entry

    def record_skip(self, url, reason):
        self.rejected.append({'url': url, 'reason': reason})


def host_of(url):
    return (urlsplit(url).hostname or '').casefold()


def parse_robots_disallow(text):
    lines = [ln.strip() for ln in text.splitlines()]
    disallow = []
    in_star_block = False
    for ln in lines:
        if not ln or ln.startswith('#') or ':' not in ln:
            continue
        key, _, value = ln.partition(':')
        key = key.strip().lower()
        value = value.strip()
        if key == 'user-agent':
            in_star_block = value == '*'
            continue
        if key == 'disallow' and in_star_block and value:
            disallow.append(value)
    return disallow


def path_disallowed(path, disallow_rules):
    for rule in disallow_rules:
        if rule == '/':
            return True
        if path.startswith(rule):
            return True
    return False


# --- Byte-preserving, Range-aware fetch for binary images (reused pattern from
# Stage 10.1/10.3's adaptation of Stage 8.6's fetch_document_bounded) ---
CONTENT_RANGE_RE = re.compile(r'bytes\s+(\d+)-(\d+)/(\d+)')
_last_request_at = {'t': None}


def _respect_rate_limit(min_interval):
    last = _last_request_at['t']
    if last is not None:
        remaining = min_interval - (time.monotonic() - last)
        if remaining > 0:
            time.sleep(remaining)


def single_range_request(session, policy, url, allowed_hosts, range_start, range_end, chunk_cap_bytes):
    _respect_rate_limit(policy.min_interval_seconds)
    headers = {'User-Agent': policy.user_agent, 'Accept': 'image/*,*/*;q=0.1',
               'Range': f'bytes={range_start}-{range_end}'}
    try:
        resp = session.get(url, timeout=policy.timeout_seconds, headers=headers, allow_redirects=True, stream=True)
    except Exception as exc:
        _last_request_at['t'] = time.monotonic()
        return None, {'url': url, 'range': f'{range_start}-{range_end}', 'error': str(exc)}
    _last_request_at['t'] = time.monotonic()

    redirect_chain = [r.url for r in resp.history] + [resp.url]
    for target in redirect_chain:
        target_host = host_of(target)
        if target_host not in allowed_hosts:
            resp.close()
            return None, {'url': url, 'range': f'{range_start}-{range_end}', 'error': f'unapproved_redirect_host:{target_host}', 'redirect_chain': redirect_chain}

    if resp.status_code in (403, 429):
        rec = {'url': url, 'range': f'{range_start}-{range_end}', 'http_status': resp.status_code, 'error': 'protected_response'}
        resp.close()
        return None, rec

    chunks = []
    size = 0
    cap = chunk_cap_bytes + 1024
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
    return {
        'status_code': resp.status_code, 'bytes': data,
        'content_range': resp.headers.get('Content-Range', ''),
        'content_length_header': resp.headers.get('Content-Length'),
        'etag': resp.headers.get('ETag'), 'last_modified': resp.headers.get('Last-Modified'),
        'final_url': resp.url, 'redirect_chain': redirect_chain,
        'content_type': resp.headers.get('Content-Type', ''),
    }, None


def fetch_bytes_bounded(session, policy, url, allowed_hosts, *, chunk_bytes, max_total_bytes, request_counter):
    log_entries = []

    def note(range_str, part, err):
        request_counter['n'] += 1
        entry = {
            'seq': request_counter['n'], 'requested_url': url, 'range': range_str,
            'http_status': part['status_code'] if part else None,
            'content_range': part.get('content_range', '') if part else '',
            'content_type': part.get('content_type', '') if part else '',
            'bytes_read': len(part['bytes']) if part else 0,
            'final_url': part.get('final_url') if part else None,
            'error': err or '',
        }
        log_entries.append(entry)
        return entry

    first, err = single_range_request(session, policy, url, allowed_hosts, 0, chunk_bytes - 1, chunk_bytes)
    note(f'0-{chunk_bytes - 1}', first, err)
    if first is None:
        return {'completeness': 'unknown_completeness', 'bytes': None, 'reason': f'probe_failed:{err}'}, log_entries

    m = CONTENT_RANGE_RE.match(first['content_range'] or '')
    if first['status_code'] == 206 and m:
        start, end, total = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if total > max_total_bytes:
            return {'completeness': 'unknown_completeness', 'bytes': None,
                    'reason': f'total_size_{total}_exceeds_cap_{max_total_bytes}', 'declared_total_bytes': total,
                    'content_type': first.get('content_type', '')}, log_entries
        parts = [(start, end, first['bytes'])]
        reference_etag, reference_last_modified = first['etag'], first['last_modified']
        next_start = end + 1
        while next_start < total:
            next_end = min(next_start + chunk_bytes - 1, total - 1)
            part, perr = single_range_request(session, policy, url, allowed_hosts, next_start, next_end, chunk_bytes)
            note(f'{next_start}-{next_end}', part, perr)
            if part is None:
                return {'completeness': 'partial', 'bytes': b''.join(p[2] for p in parts),
                        'reason': f'assembly_stopped_early:{perr}', 'declared_total_bytes': total}, log_entries
            pm = CONTENT_RANGE_RE.match(part['content_range'] or '')
            if part['status_code'] != 206 or not pm:
                return {'completeness': 'partial', 'bytes': b''.join(p[2] for p in parts),
                        'reason': 'server_stopped_honoring_range', 'declared_total_bytes': total}, log_entries
            p_start, p_end, p_total = int(pm.group(1)), int(pm.group(2)), int(pm.group(3))
            if p_total != total or (reference_etag and part['etag'] and part['etag'] != reference_etag) or \
               (reference_last_modified and part['last_modified'] and part['last_modified'] != reference_last_modified):
                return {'completeness': 'unknown_completeness', 'bytes': None,
                        'reason': 'aborted_version_mismatch_between_parts', 'declared_total_bytes': total}, log_entries
            parts.append((p_start, p_end, part['bytes']))
            next_start = p_end + 1
        assembled = b''.join(p[2] for p in sorted(parts, key=lambda x: x[0]))
        complete = len(assembled) == total
        return {'completeness': 'complete' if complete else 'partial', 'bytes': assembled,
                'reason': 'assembled_size_matches_declared_total' if complete else 'assembled_size_mismatch',
                'declared_total_bytes': total, 'bytes_assembled': len(assembled),
                'content_type': first.get('content_type', '')}, log_entries

    content_length = first['content_length_header']
    if first['status_code'] == 200 and content_length and content_length.isdigit():
        total = int(content_length)
        if total > max_total_bytes:
            return {'completeness': 'unknown_completeness', 'bytes': None,
                    'reason': f'range_unsupported_and_content_length_{total}_exceeds_cap', 'declared_total_bytes': total}, log_entries
        if len(first['bytes']) == total:
            return {'completeness': 'complete', 'bytes': first['bytes'],
                    'reason': 'range_unsupported_but_full_content_length_read_in_one_bounded_request',
                    'declared_total_bytes': total, 'content_type': first.get('content_type', '')}, log_entries
        return {'completeness': 'partial', 'bytes': first['bytes'],
                'reason': 'range_unsupported_content_length_exceeds_single_bounded_read',
                'declared_total_bytes': total}, log_entries
    return {'completeness': 'unknown_completeness', 'bytes': first['bytes'] if first else None,
            'reason': 'range_unsupported_and_no_reliable_content_length',
            'content_type': first.get('content_type', '') if first else ''}, log_entries
