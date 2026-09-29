"""Stage 11.2 phase 1 -- fetch the product page fresh, compare it against
Stage 11's saved snapshot, and run the CORRECTED gallery extraction (DOM
data-media-id/data-fancybox grouping, not filename substring matching) with
an explicit completeness assertion against the known count."""
import hashlib
import json
import re

from lib import OUT, RequestLogger, load_budget, make_probe
from product_tool.census.models import EndpointCapability

ROOT_STAGE11 = OUT.parent / 'source_census_2026-09-23_stage11'

budget = load_budget()
allowed_hosts = tuple(budget['allowed_hosts'])
probe = make_probe(budget, max_bytes_key='max_response_bytes_per_request_pages')
logger = RequestLogger()

url = 'https://hyperx.com/products/hyperx-quadcast-2-s-usb-microphone'
result = probe.probe(url, allowed_hosts=allowed_hosts, capability=EndpointCapability.PRODUCT_PAGE, sample_type='product_page_refetch')
entry = logger.record(url, EndpointCapability.PRODUCT_PAGE, result, note='re-fetch of the same Stage 11 URL, to compare against the saved snapshot')

fresh_html = getattr(result, 'diagnostic_text', '') or ''
(OUT / 'raw').mkdir(parents=True, exist_ok=True)
(OUT / 'raw' / 'hyperx_quadcast_2s_product_page_fresh.html.txt').write_text(fresh_html, encoding='utf-8', errors='replace')

saved_html = (ROOT_STAGE11 / 'raw/hyperx_quadcast_2s_product_page.html.txt').read_text(encoding='utf-8', errors='replace')


def extract_gallery(html):
    items = []
    seen = set()
    for m in re.finditer(r'data-media-id="(\d+)"', html):
        mid = m.group(1)
        if mid in seen:
            continue
        chunk = html[m.start():m.start() + 1400]
        href_m = re.search(r'data-fancybox="images" href="([^"]+)"', chunk)
        if href_m:
            seen.add(mid)
            href = href_m.group(1)
            items.append({'media_id': mid, 'url': ('https:' + href) if href.startswith('//') else href})
    return items


fresh_gallery = extract_gallery(fresh_html)
saved_gallery = extract_gallery(saved_html)

comparison = {
    'saved_html_sha256': hashlib.sha256(saved_html.encode()).hexdigest(),
    'fresh_html_sha256': hashlib.sha256(fresh_html.encode()).hexdigest(),
    'html_byte_identical': saved_html == fresh_html,
    'saved_gallery_count': len(saved_gallery),
    'fresh_gallery_count': len(fresh_gallery),
    'saved_gallery_urls': [g['url'] for g in saved_gallery],
    'fresh_gallery_urls': [g['url'] for g in fresh_gallery],
    'gallery_urls_identical_set': set(g['url'] for g in saved_gallery) == set(g['url'] for g in fresh_gallery),
}

COMPLETENESS_EXPECTED = 14


def completeness_check(gallery, label):
    ok = len(gallery) == COMPLETENESS_EXPECTED
    return {
        'label': label,
        'expected': COMPLETENESS_EXPECTED,
        'found': len(gallery),
        'complete': ok,
        'method': 'DOM data-media-id groups paired with their data-fancybox="images" href, not a filename/SKU substring filter',
    }


output = {
    'phase': 'fresh_product_page_and_gallery_fix',
    'http_status': result.http_status,
    'access_status': result.access_status.value,
    'bytes_read': entry['bytes_read'],
    'comparison_to_stage11_snapshot': comparison,
    'corrected_gallery_completeness_check_fresh_page': completeness_check(fresh_gallery, 'fresh_fetch_this_stage'),
    'corrected_gallery_completeness_check_stage11_snapshot': completeness_check(saved_gallery, 'stage11_saved_snapshot_reread'),
    'gallery_items_fresh': fresh_gallery,
    'request_log': logger.entries,
}
(OUT / 'phase1_fresh_product_page_and_gallery_fix.json').write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding='utf-8')
print('html_byte_identical:', comparison['html_byte_identical'])
print('fresh gallery count:', len(fresh_gallery), '/ expected', COMPLETENESS_EXPECTED)
print('saved gallery count:', len(saved_gallery), '/ expected', COMPLETENESS_EXPECTED)
