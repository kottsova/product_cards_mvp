"""Stage 8.1 bounded supplemental fetch: at most one extra nav + one extra
product page for xiaomi_global and hyperx, reusing Stage 8's own safety
primitives (AccessProbe / ProbePolicy / inspect_structure). No invented
catalog-model URLs: only first-party navigation links discovered on an
already-verified official page. Stops immediately on 403/429/challenge for
a host and does not retry.
"""
import json
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))

from product_tool.census.endpoint_probe import AccessProbe, ProbePolicy
from product_tool.census.models import EndpointCapability
from product_tool.census.structural_contracts_v8 import inspect_structure

OUT = Path('reports/source_census_2026-09-22_stage8_1')
(OUT / 'fixtures').mkdir(parents=True, exist_ok=True)

probe = AccessProbe(policy=ProbePolicy(timeout_seconds=6, max_bytes=700_000, min_interval_seconds=1.5))

attempts = []
blocked_hosts = set()

def protected(result):
    return result.http_status in (403, 429) or result.protection_status.value in (
        'challenge_detected', 'captcha_detected', 'challenge_confirmed', 'browser_verification_required'
    ) or result.access_status.value in ('captcha_or_blocked', 'rate_limited')


def fetch(url, hosts, kind):
    host = urlsplit(url).hostname
    if host in blocked_hosts:
        return None, 'host_paused_this_run'
    cap = EndpointCapability.PRODUCT_PAGE if kind == 'product' else EndpointCapability.HOMEPAGE
    result = probe.probe(url, allowed_hosts=hosts, capability=cap, sample_type=kind)
    attempts.append({
        'url': url, 'kind': kind, 'http_status': result.http_status,
        'access_status': result.access_status.value, 'protection_status': result.protection_status.value,
        'checked_at': result.checked_at,
    })
    if protected(result):
        blocked_hosts.add(host)
        return None, 'protected_response_stopping_host'
    if result.http_status != 200:
        return None, f'http_{result.http_status}'
    struct = inspect_structure(result.diagnostic_text, result.final_url, hosts)
    return {'url': url, 'final_url': result.final_url, 'struct': struct}, None


def save_fixture(struct):
    sha = struct['content_sha256']
    path = OUT / 'fixtures' / f'{sha}.json'
    payload = {k: v for k, v in struct.items() if k != 'links'}
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')
    return f'fixtures/{sha}.json'


results = {}

# --- Xiaomi Global: get one more product page in a different category ---
xiaomi_hosts = ('mi.com',)
nav, err = fetch('https://www.mi.com/global/', xiaomi_hosts, 'homepage')
if nav:
    already = {'https://www.mi.com/global/product/leica-leitzphone-powered-by-xiaomi/'}
    candidates = [l for l in nav['struct']['links'] if l['kind'] == 'product' and l['url'] not in already]
    # prefer a candidate whose path segment differs from the already-sampled 'product' slug pattern (any distinct product is fine; take first few and try until one succeeds)
    picked = None
    for c in candidates[:3]:
        page, perr = fetch(c['url'], xiaomi_hosts, 'product')
        if page:
            picked = (c['url'], page)
            break
    results['xiaomi_global'] = {
        'nav_url': nav['url'], 'nav_fixture': save_fixture(nav['struct']),
        'candidates_seen': [c['url'] for c in candidates[:5]],
        'picked': picked[0] if picked else None,
        'picked_fixture': save_fixture(picked[1]['struct']) if picked else None,
        'picked_struct': picked[1]['struct'] if picked else None,
        'error': None if picked else 'no_new_product_link_resolved',
    }
else:
    results['xiaomi_global'] = {'error': err}

time.sleep(1.5)

# --- HyperX: get one more product page outside the 'bundles' collection ---
hyperx_hosts = ('hyperx.com',)
nav, err = fetch('https://hyperx.com/pages/support', hyperx_hosts, 'support')
if nav:
    already = {'https://hyperx.com/products/hyperx-bundle-alloy-rise-75-keyboard-pulsefire-haste-2-s-wireless-mouse'}
    candidates = [l for l in nav['struct']['links'] if l['kind'] in ('product', 'category') and l['url'] not in already]
    cat_candidates = [c for c in candidates if c['kind'] == 'category' and 'bundle' not in c['url'].lower()]
    picked = None
    tried_urls = []
    # First try any directly-linked product URL from the support page.
    for c in [c for c in candidates if c['kind'] == 'product'][:3]:
        tried_urls.append(c['url'])
        page, perr = fetch(c['url'], hyperx_hosts, 'product')
        if page:
            picked = (c['url'], page)
            break
    # If none, walk into one non-bundle category page and take a product link from there.
    if not picked and cat_candidates:
        cat_page, cat_err = fetch(cat_candidates[0]['url'], hyperx_hosts, 'category')
        if cat_page:
            sub_candidates = [l for l in cat_page['struct']['links'] if l['kind'] == 'product' and l['url'] not in already]
            for c in sub_candidates[:2]:
                tried_urls.append(c['url'])
                page, perr = fetch(c['url'], hyperx_hosts, 'product')
                if page:
                    picked = (c['url'], page)
                    break
    results['hyperx'] = {
        'nav_url': nav['url'], 'nav_fixture': save_fixture(nav['struct']),
        'category_candidates_seen': [c['url'] for c in cat_candidates[:5]],
        'product_urls_tried': tried_urls,
        'picked': picked[0] if picked else None,
        'picked_fixture': save_fixture(picked[1]['struct']) if picked else None,
        'picked_struct': picked[1]['struct'] if picked else None,
        'error': None if picked else 'no_new_product_link_resolved',
    }
else:
    results['hyperx'] = {'error': err}

(OUT / 'supplemental_fetch_attempts.json').write_text(json.dumps(attempts, indent=2, ensure_ascii=False), encoding='utf-8')
(OUT / 'supplemental_fetch_results.json').write_text(json.dumps(results, indent=2, ensure_ascii=False, default=str), encoding='utf-8')

print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != 'picked_struct'} for k, v in results.items()}, indent=2, ensure_ascii=False))
print('BLOCKED HOSTS:', blocked_hosts)
