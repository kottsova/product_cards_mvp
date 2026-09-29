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
    cap = EndpointCapability.PRODUCT_PAGE if kind == 'product' else EndpointCapability.HOMEPAGE if kind == 'homepage' else EndpointCapability.CATEGORY_PAGE
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


hosts = ('de.dreametech.com',)
already = {'https://de.dreametech.com/products/a2', 'https://de.dreametech.com/products/aqua10-roller-saugroboter', 'https://de.dreametech.com/products/d10-plus-gen-2'}

nav = fetch('https://de.dreametech.com/', hosts, 'homepage')
picked = None
tried = []
if nav:
    prods = [l for l in nav['struct']['links'] if l['kind'] == 'product' and l['url'] not in already]
    for c in prods[:3]:
        tried.append(c['url'])
        time.sleep(1.5)
        page = fetch(c['url'], hosts, 'product')
        if page and page['struct']['is_product_page']:
            picked = page
            break

results.setdefault('dreame_de_live', {})
results['dreame_de_live']['nav_url'] = 'https://de.dreametech.com/'
results['dreame_de_live']['nav_fixture'] = save_fixture(nav['struct']) if nav else None
results['dreame_de_live']['product_urls_tried'] = tried
results['dreame_de_live']['picked'] = picked['url'] if picked else None
results['dreame_de_live']['picked_fixture'] = save_fixture(picked['struct']) if picked else None
results['dreame_de_live']['picked_struct'] = picked['struct'] if picked else None
results['dreame_de_live']['error'] = None if picked else 'no_new_product_link_resolved'

(OUT / 'supplemental_fetch_attempts.json').write_text(json.dumps(attempts, indent=2, ensure_ascii=False), encoding='utf-8')
(OUT / 'supplemental_fetch_results.json').write_text(json.dumps(results, indent=2, ensure_ascii=False, default=str), encoding='utf-8')
print(json.dumps({k: v for k, v in results['dreame_de_live'].items() if k != 'picked_struct'}, indent=2, ensure_ascii=False))
