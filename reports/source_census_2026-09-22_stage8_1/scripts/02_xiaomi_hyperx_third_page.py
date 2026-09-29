import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from product_tool.census.endpoint_probe import AccessProbe, ProbePolicy
from product_tool.census.models import EndpointCapability
from product_tool.census.structural_contracts_v8 import inspect_structure

OUT = Path('reports/source_census_2026-09-22_stage8_1')
probe = AccessProbe(policy=ProbePolicy(timeout_seconds=6, max_bytes=700_000, min_interval_seconds=1.5))
attempts = json.loads((OUT / 'supplemental_fetch_attempts.json').read_text(encoding='utf-8'))
results = json.loads((OUT / 'supplemental_fetch_results.json').read_text(encoding='utf-8'))


def protected(result):
    return result.http_status in (403, 429) or result.protection_status.value in (
        'challenge_detected', 'captcha_detected', 'challenge_confirmed', 'browser_verification_required'
    ) or result.access_status.value in ('captcha_or_blocked', 'rate_limited')


def fetch(url, hosts, kind):
    cap = EndpointCapability.PRODUCT_PAGE if kind == 'product' else EndpointCapability.HOMEPAGE
    result = probe.probe(url, allowed_hosts=hosts, capability=cap, sample_type=kind)
    attempts.append({
        'url': url, 'kind': kind, 'http_status': result.http_status,
        'access_status': result.access_status.value, 'protection_status': result.protection_status.value,
        'checked_at': result.checked_at,
    })
    if protected(result) or result.http_status != 200:
        return None
    return {'url': url, 'final_url': result.final_url, 'struct': inspect_structure(result.diagnostic_text, result.final_url, hosts)}


def save_fixture(struct):
    sha = struct['content_sha256']
    path = OUT / 'fixtures' / f'{sha}.json'
    payload = {k: v for k, v in struct.items() if k != 'links'}
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')
    return f'fixtures/{sha}.json'


page = fetch('https://www.mi.com/global/product/xiaomi-watch-s5-46mm/', ('mi.com',), 'product')
if page:
    results['xiaomi_global']['third_page'] = page['url']
    results['xiaomi_global']['third_fixture'] = save_fixture(page['struct'])
    results['xiaomi_global']['third_struct'] = page['struct']
time.sleep(1.5)

page = fetch('https://hyperx.com/collections/gaming-headsets', ('hyperx.com',), 'category')
headset_url = None
if page:
    prods = [l for l in page['struct']['links'] if l['kind'] == 'product']
    if prods:
        headset_url = prods[0]['url']
if headset_url:
    time.sleep(1.5)
    page2 = fetch(headset_url, ('hyperx.com',), 'product')
    if page2:
        results['hyperx']['third_page'] = page2['url']
        results['hyperx']['third_fixture'] = save_fixture(page2['struct'])
        results['hyperx']['third_struct'] = page2['struct']

(OUT / 'supplemental_fetch_attempts.json').write_text(json.dumps(attempts, indent=2, ensure_ascii=False), encoding='utf-8')
(OUT / 'supplemental_fetch_results.json').write_text(json.dumps(results, indent=2, ensure_ascii=False, default=str), encoding='utf-8')
print(json.dumps({k: {kk: vv for kk, vv in v.items() if 'struct' not in kk} for k, v in results.items()}, indent=2, ensure_ascii=False))
