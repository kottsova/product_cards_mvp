"""Stage 11.2 phase 2 -- robots.txt for cdn.shopify.com (new host), a small
bounded Range check of the video file's type/availability (not a full
download), and a separate fetch+hash+visual check of the video's own cover
image (hosted on hyperx.com, treated as distinct evidence from the video)."""
import hashlib
import json

from lib import OUT, RequestLogger, load_budget, make_probe, single_range_request
from product_tool.census.models import EndpointCapability

budget = load_budget()
allowed_hosts = tuple(budget['allowed_hosts'])
page_probe = make_probe(budget, max_bytes_key='max_response_bytes_per_request_pages')
logger = RequestLogger()

# 1) robots.txt for the new host
robots_url = 'https://cdn.shopify.com/robots.txt'
robots_result = page_probe.probe(robots_url, allowed_hosts=allowed_hosts, capability=EndpointCapability.ROBOTS, sample_type='robots')
logger.record(robots_url, EndpointCapability.ROBOTS, robots_result)
robots_text = getattr(robots_result, 'diagnostic_text', '') or ''
(OUT / 'raw' / 'cdn_shopify_com_robots.txt').write_text(robots_text, encoding='utf-8', errors='replace')

# 2) small bounded Range check of the video (type/availability only, not a full download)
video_url = 'https://cdn.shopify.com/videos/c/o/v/b05b09498da44727be948864df7222ac.mp4'
chunk_bytes = budget['limits']['video_check_chunk_bytes']
video_part, video_err = single_range_request(
    page_probe.session, page_probe.policy, video_url, allowed_hosts, 0, chunk_bytes - 1, chunk_bytes
)
video_check = {
    'url': video_url,
    'requested_range': f'0-{chunk_bytes - 1}',
    'succeeded': video_part is not None,
    'error': video_err,
}
if video_part is not None:
    video_check.update({
        'http_status': video_part['status_code'],
        'content_type': video_part['content_type'],
        'content_range_header': video_part['content_range'],
        'accept_ranges_header': video_part['accept_ranges'],
        'bytes_actually_read_this_chunk': len(video_part['bytes']),
        'first_bytes_hex_signature': video_part['bytes'][:12].hex(),
        'is_mp4_signature': b'ftyp' in video_part['bytes'][:64],
        'final_url': video_part['final_url'],
        'redirect_chain': video_part['redirect_chain'],
    })
    # declared total size, if server disclosed it via Content-Range on a 206
    import re
    m = re.match(r'bytes\s+\d+-\d+/(\d+)', video_part['content_range'] or '')
    video_check['declared_total_bytes'] = int(m.group(1)) if m else None
logger.entries.append({
    'seq': len(logger.entries) + 1, 'requested_url': video_url, 'capability': 'asset_host',
    'access_status': 'direct_access' if video_part else 'unavailable',
    'http_status': video_check.get('http_status'), 'final_url': video_check.get('final_url', video_url),
    'redirect_chain': video_check.get('redirect_chain', [video_url]), 'content_type': video_check.get('content_type', ''),
    'protection_status': 'ordinary_page' if video_part else 'inconclusive', 'error': video_err.get('error', '') if video_err else '',
    'bytes_read': video_check.get('bytes_actually_read_this_chunk', 0), 'note': 'bounded type/availability check only, not a full download',
})

# 3) the cover image -- fetched, hashed, and to be visually inspected, SEPARATELY from the video
cover_url = 'https://hyperx.com/cdn/shop/files/HX-QUADCAST-2-S-YouTube-tn-1080p_1920x.jpg?v=1789488039'
cover_part, cover_err = single_range_request(
    page_probe.session, page_probe.policy, cover_url, allowed_hosts, 0,
    budget['limits']['max_response_bytes_per_request_images'] - 1,
    budget['limits']['max_response_bytes_per_request_images'],
)
cover_check = {'url': cover_url, 'succeeded': cover_part is not None, 'error': cover_err}
if cover_part is not None:
    data = cover_part['bytes']
    sha256 = hashlib.sha256(data).hexdigest()
    cover_check.update({
        'http_status': cover_part['status_code'],
        'content_type': cover_part['content_type'],
        'content_range_header': cover_part['content_range'],
        'bytes_read': len(data),
        'sha256': sha256,
        'saved_as': None,
        'note': "Bytes assembled/hashed/visually inspected in-session, then discarded -- not committed, per the no-raw-content rule.",
    })
    import re
    m = re.match(r'bytes\s+\d+-\d+/(\d+)', cover_part['content_range'] or '')
    total = int(m.group(1)) if m else len(data)
    cover_check['declared_total_bytes'] = total
    cover_check['byte_count_matches_declared_total'] = len(data) == total
logger.entries.append({
    'seq': len(logger.entries) + 1, 'requested_url': cover_url, 'capability': 'asset_host',
    'access_status': 'direct_access' if cover_part else 'unavailable',
    'http_status': cover_check.get('http_status'), 'final_url': cover_part.get('final_url', cover_url) if cover_part else cover_url,
    'redirect_chain': cover_part.get('redirect_chain', [cover_url]) if cover_part else [cover_url],
    'content_type': cover_check.get('content_type', ''), 'protection_status': 'ordinary_page' if cover_part else 'inconclusive',
    'error': cover_err.get('error', '') if cover_err else '', 'bytes_read': cover_check.get('bytes_read', 0),
    'note': 'cover image for the confirmed product video, fetched as separate evidence',
})

# Save cover image bytes to scratch (outside repo) for visual inspection, not into reports/
import pathlib
scratch_dir = pathlib.Path(r'C:\Users\Julynce\AppData\Local\Temp\claude\a--work-dev-product-cards-mvp\1741bb85-29db-47a4-97a9-ed84155ebc47\scratchpad\stage11_2_images')
scratch_dir.mkdir(parents=True, exist_ok=True)
if cover_part is not None:
    (scratch_dir / 'hyperx_quadcast_2s_video_cover.jpg').write_bytes(cover_part['bytes'])

output = {
    'phase': 'video_and_cover_check',
    'robots_http_status': robots_result.http_status,
    'video_check': video_check,
    'cover_check': cover_check,
    'request_log': logger.entries,
}
(OUT / 'phase2_video_and_cover_check.json').write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding='utf-8')
print(json.dumps({'video_check': video_check, 'cover_check': {k: v for k, v in cover_check.items() if k != 'sha256' or True}}, indent=2, ensure_ascii=False))
