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
OUT = ROOT / 'reports/source_census_2026-09-23_stage11_2'


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


# --- Byte-preserving Range fetch (same pattern as Stage 10.1/10.3/11.1) ---
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
    headers = {'User-Agent': policy.user_agent, 'Accept': '*/*',
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
    for chunk in resp.iter_content(chunk_size=16_384):
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
        'accept_ranges': resp.headers.get('Accept-Ranges', ''),
    }, None
