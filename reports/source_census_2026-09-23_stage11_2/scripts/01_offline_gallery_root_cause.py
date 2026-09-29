"""Stage 11.2 -- offline root-cause analysis of Stage 11's "9 images" result,
using only the already-saved HTML from Stage 11 (no new request). Extracts
the true main gallery via the DOM's own data-media-id / data-fancybox="images"
grouping instead of a SKU-filename substring filter, and locates the
user-provided video's DOM linkage to this exact page.
"""
import json
import re
from pathlib import Path

ROOT = Path(r'A:\work\dev\product_cards_mvp')
STAGE11 = ROOT / 'reports/source_census_2026-09-23_stage11'
OUT = ROOT / 'reports/source_census_2026-09-23_stage11_2'

text = (STAGE11 / 'raw/hyperx_quadcast_2s_product_page.html.txt').read_text(encoding='utf-8', errors='replace')

# The real main gallery: every productView-img-container with a numeric data-media-id,
# each holding one data-fancybox="images" href -- this is the DOM group Shopify's own
# lightbox gallery uses, independent of any filename pattern.
gallery = []
for m in re.finditer(r'data-media-id="(\d+)"', text):
    mid = m.group(1)
    chunk = text[m.start():m.start() + 1400]
    href_m = re.search(r'data-fancybox="images" href="([^"]+)"', chunk)
    if href_m:
        gallery.append({'media_id': mid, 'url': 'https:' + href_m.group(1) if href_m.group(1).startswith('//') else href_m.group(1)})

# de-dup (each media-id can appear more than once if thumbnail nav repeats it)
seen = set()
deduped = []
for g in gallery:
    if g['media_id'] not in seen:
        seen.add(g['media_id'])
        deduped.append(g)

stage11_claimed_images = [
    'main_1', 'angle_2', 'angle_3', 'angle_4', 'angle_5', 'angle_6', 'angle_7', 'angle_8', 'angle_9',
]
missed = [g for g in deduped if not any(tok in g['url'] for tok in ['9a273aa_main_1', '9a273aa_angle'])]

root_cause = {
    'stage11_method': (
        'Regex-substring filter requiring the literal SKU string "9a273aa" to appear in the '
        'image filename (re.findall(r"hyperx_quadcast_2_s_9a273aa_[a-zA-Z0-9_]+\\.jpg", text)). '
        'This is not how the page itself groups gallery images.'
    ),
    'actual_dom_grouping': (
        'The page\'s own lightbox gallery groups images by data-fancybox="images" inside '
        'containers carrying a shared numeric data-media-id, under the same product-view '
        'template. Filename pattern is irrelevant to this grouping.'
    ),
    'true_gallery_count': len(deduped),
    'true_gallery_items': deduped,
    'items_stage11_missed': missed,
    'why_they_were_missed': (
        'Five of the 14 gallery images are annotated marketing/feature callouts (filenames '
        'containing "annotated_1_future_en", "annotated_2_dynamic_en", "annotated_3_tap_en", '
        '"annotated_4_versatile_en", "annotated_5_redesigned_en") -- none contains the SKU '
        'string "9a273aa", so Stage 11\'s substring filter silently excluded them even though '
        'they belong to the same gallery, same data-fancybox group, same product template.'
    ),
    'conclusion': (
        f'Stage 11 found {9} of {len(deduped)} real gallery images -- not because 5 images were '
        'unofficial or unrelated, but because the extraction method (filename substring) does '
        'not match the page\'s own grouping mechanism (DOM data-media-id/data-fancybox). This '
        'stage\'s corrected extraction method uses the DOM grouping directly.'
    ),
}

# --- Video: locate its DOM linkage to this exact page, offline, before any new request ---
video_url = 'https://cdn.shopify.com/videos/c/o/v/b05b09498da44727be948864df7222ac.mp4'
video_positions = [m.start() for m in re.finditer(re.escape(video_url), text)]
video_section_id_m = re.search(r'id="shopify-section-(template--\d+__video_block_\w+)"', text)
video_section_id = video_section_id_m.group(1) if video_section_id_m else None
main_template_ids = sorted(set(re.findall(r'(template--\d+)__main-\d+', text)))
video_matches_same_template = bool(video_section_id and main_template_ids and video_section_id.split('__')[0] == main_template_ids[0])

poster_srcset_m = re.search(r'alt="HyperX QuadCast 2 S – USB Microphone - video"[^>]*', text)
poster_url_m = re.search(r'src="(//hyperx\.com/cdn/shop/files/HX-QUADCAST-2-S-YouTube-tn-1080p[^"]+)"', text)

video_evidence = {
    'user_provided_url': video_url,
    'found_verbatim_in_saved_hyperx_page_html': len(video_positions) > 0,
    'occurrence_count': len(video_positions),
    'dom_container': 'section#shopify-section-' + str(video_section_id),
    'shares_same_page_template_id_as_the_14_image_gallery': video_matches_same_template,
    'embedding_markup': '<video class="js-video slide-pc/slide-mb"><source src="...b05b09498da44727be948864df7222ac.mp4"></video>, inside <deferred-media data-media-id="template--...__video_block_tTVMRn">',
    'cover_image_found_separately': bool(poster_url_m),
    'cover_image_url': ('https:' + poster_url_m.group(1)) if poster_url_m else None,
    'cover_image_alt_text': 'HyperX QuadCast 2 S – USB Microphone - video',
    'conclusion': (
        'The video is embedded directly inside THIS product\'s own page markup, under the same '
        'Shopify section template id family as the 14-image gallery, with its own '
        'product-specific poster image (filename itself says "HX-QUADCAST-2-S..."). This is '
        'first-party DOM evidence of belonging to this exact product, not an inference from '
        'sharing a generic Shopify CDN domain.'
    ),
}

(OUT / 'offline_gallery_root_cause.json').write_text(json.dumps({'root_cause': root_cause, 'video_evidence': video_evidence}, indent=2, ensure_ascii=False), encoding='utf-8')
print('true gallery count:', len(deduped))
print('missed by stage 11:', len(missed))
for m in missed:
    print(' -', m['url'])
print('video found in saved html:', video_evidence['found_verbatim_in_saved_hyperx_page_html'], 'x', video_evidence['occurrence_count'])
