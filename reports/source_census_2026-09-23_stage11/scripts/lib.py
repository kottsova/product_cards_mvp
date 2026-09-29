import json
import sys
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, r'A:\work\dev\product_cards_mvp')

from product_tool.census.endpoint_probe import AccessProbe, ProbePolicy
from product_tool.census.models import EndpointCapability  # noqa: F401

ROOT = Path(r'A:\work\dev\product_cards_mvp')
OUT = ROOT / 'reports/source_census_2026-09-23_stage11'


def load_budget():
    return json.loads((OUT / 'budget_predeclaration.json').read_text(encoding='utf-8'))


def make_probe(budget):
    limits = budget['limits']
    policy = ProbePolicy(
        timeout_seconds=limits['timeout_seconds_per_request'],
        max_bytes=limits['max_response_bytes_per_request'],
        min_interval_seconds=limits['min_interval_seconds_between_requests'],
    )
    return AccessProbe(policy=policy)


class RequestLogger:
    def __init__(self):
        self.entries = []

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


def host_of(url):
    return (urlsplit(url).hostname or '').casefold()
