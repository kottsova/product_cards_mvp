"""Stage 10.1 phase 4 -- bounded, Range-aware fetch of the CMS content sitemap
chunk, per budget_revision_1_document_fetch.json (declared before this request)."""
import gzip
import json

from lib import OUT, load_budget, make_probe
from lib import fetch_document_bounded

budget = load_budget()
allowed_hosts = tuple(budget['allowed_hosts'])
revision = json.loads((OUT / 'budget_revision_1_document_fetch.json').read_text(encoding='utf-8'))
probe = make_probe(budget)

url = 'https://www.xbox.com/sitemap/cms-sitemap-0.xml.gz'
counter = {'n': 0}
result, log_entries = fetch_document_bounded(
    probe.session, probe.policy, url, allowed_hosts,
    chunk_bytes=revision['revision']['chunk_bytes_per_range_request'],
    max_total_bytes=revision['revision']['max_document_total_bytes'],
    request_counter=counter,
)

decoded_text = ''
url_count = 0
sample_urls = []
if result['completeness'] == 'complete' and result['bytes']:
    try:
        decoded_text = gzip.decompress(result['bytes']).decode('utf-8', errors='replace')
        import re
        locs = re.findall(r'<loc>([^<]+)</loc>', decoded_text)
        url_count = len(locs)
        sample_urls = locs
    except Exception as exc:
        decoded_text = f'<gzip decompress failed: {exc}>'

output = {
    'phase': 'cms_sitemap_fetch',
    'url': url,
    'completeness': result['completeness'],
    'reason': result.get('reason'),
    'declared_total_bytes': result.get('declared_total_bytes'),
    'bytes_assembled': result.get('bytes_assembled'),
    'gzip_decompressed_ok': bool(decoded_text) and not decoded_text.startswith('<gzip'),
    'url_count_found': url_count,
    'request_log': log_entries,
}
(OUT / 'phase4_cms_sitemap_fetch.json').write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding='utf-8')
if decoded_text and not decoded_text.startswith('<gzip'):
    (OUT / 'raw' / 'cms_sitemap_0.xml').write_text(decoded_text, encoding='utf-8', errors='replace')
print(json.dumps(output, indent=2, ensure_ascii=False)[:3000])
print('---all urls---' if url_count < 300 else '---too many to print, saved to raw/---')
if url_count < 300:
    for u in sample_urls:
        print(u)
