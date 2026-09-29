"""Stage 10.3 -- offline DOM/gallery analysis of the Stage 10.1-saved Xbox
Series S landing page. No new network requests. Finds every image tied to the
live variant selector via DOM structure (the "hero-gallery" per-option
carousel), confirms whether a Carbon Black (s-new) gallery slot exists at all,
and separately inventories generic/feature images that show a console but are
NOT tied to any color option, as small-number visual-check candidates.
"""
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(r'A:\work\dev\product_cards_mvp')
STAGE10_1 = ROOT / 'reports/source_census_2026-09-23_stage10_1'
OUT = ROOT / 'reports/source_census_2026-09-23_stage10_3'

text = (STAGE10_1 / 'raw/series_s_landing_en_us.html.txt').read_text(encoding='utf-8', errors='replace')


def comment_spans(s):
    spans = []
    for m in re.finditer(r'<!--', s):
        end = s.find('-->', m.start())
        spans.append((m.start(), (end + 3) if end != -1 else len(s)))
    return spans


SPANS = comment_spans(text)


def is_commented(pos):
    return any(a <= pos < b for a, b in SPANS)


findings = {}

# --- 1. The per-option hero-gallery carousel: does a Carbon Black (s-new) slot exist? ---
gallery_slot_ids = {
    'standard (512GB Robot White)': ['standard-slide1', 'standard-slide2', 'standard-slide3', 'standard-slide4'],
    'special (1TB Robot White)': ['special-slide1', 'special-slide2', 'special-slide3', 'special-slide4'],
    'new (1TB Carbon Black) -- expected but searched for': ['new-slide1', 'new-slide2', 'new-slide3', 'new-slide4'],
}
slot_presence = {}
for label, ids in gallery_slot_ids.items():
    slot_presence[label] = {sid: (text.find(f'id=\\"{sid}\\"') > 0 or f'id="{sid}"' in text) for sid in ids}

campsite_names = sorted(set(re.findall(r'campsiteName\\":\\"([^\\"]+)\\"', text)))
findings['hero_gallery_carousel'] = {
    'slot_presence_by_option': slot_presence,
    'campsite_names_found': campsite_names,
    'conclusion': (
        'The page\'s own per-option hero image carousel ("hero-gallery", driven by the same '
        'live variant selector as the purchase buttons) has dedicated slide sets for '
        '"standard" (512GB Robot White, campsiteName "page-hero-standard") and "special" '
        '(1TB Robot White, implied by the "special-slideN" ids) -- but NO "new-slideN" set and '
        'no "page-hero-new" campsite exists anywhere in the saved page. This is a structural, '
        'not just a filename-based, confirmation: the official page\'s own image-gallery '
        'infrastructure has no dedicated photography slot for the Carbon Black 1TB option at '
        'all, in this snapshot.'
    ),
}

# --- 2. Full live <img> inventory from BOTH known Xbox asset CDN hosts ---
KNOWN_ASSET_HOSTS = {'cms-assets.xboxservices.com', 'assets.xboxservices.com'}
inventory = []
marker = '\\u003'
seen_pos = set()
for m in re.finditer(r'<img\b[^>]*>', text):
    if is_commented(m.start()) or m.start() in seen_pos:
        continue
    tag = m.group(0)
    if marker in tag:
        continue
    src_m = re.search(r'src="([^"]+)"', tag) or re.search(r'srcset="([^"]+)"', tag)
    alt_m = re.search(r'alt="([^"]*)"', tag)
    if not src_m:
        continue
    host = urlsplit(src_m.group(1)).hostname or ''
    if host not in KNOWN_ASSET_HOSTS:
        continue
    seen_pos.add(m.start())
    inventory.append({'pos': m.start(), 'host': host, 'src': src_m.group(1), 'alt': alt_m.group(1) if alt_m else None})

inventory.sort(key=lambda r: r['pos'])
findings['live_image_inventory_both_cdn_hosts'] = inventory

# --- 3. Classify each inventory item ---
white_bundle_confirmed = [r for r in inventory if 'robot white' in (r['alt'] or '').lower()]
white_bundle_asset_ids = {'389964'}  # the one numeric bundle-id prefix confirmed White throughout
carbon_aware_env = [r for r in inventory if 'carbon-aware' in r['src'].lower() or 'surrounded by leaves' in (r['alt'] or '').lower()]
refurbished = [r for r in inventory if 'refurbished' in (r['alt'] or '').lower() or 'refurbished' in r['src'].lower()]
dimension_diagram = [r for r in inventory if 'diagram' in (r['alt'] or '').lower()]
no_console_visible = [r for r in inventory if 'screenshot' in (r['alt'] or '').lower() or 'television' in (r['alt'] or '').lower()]


def already_classified(r):
    return (
        r in white_bundle_confirmed or r in carbon_aware_env or r in refurbished
        or r in dimension_diagram or r in no_console_visible
        or any(pid in r['src'] for pid in white_bundle_asset_ids)
    )


generic_console_no_color_stated = [
    r for r in inventory
    if not already_classified(r)
    and ('xbox series s' in (r['alt'] or '').lower() or 'back of the xbox' in (r['alt'] or '').lower())
]

findings['classification'] = {
    'rejected_confirmed_white_by_alt_text_or_shared_bundle_id': [
        r for r in inventory if r in white_bundle_confirmed or any(pid in r['src'] for pid in white_bundle_asset_ids)
    ],
    'rejected_environmental_illustration_not_color_evidence': carbon_aware_env,
    'rejected_different_product_refurbished_listing': refurbished,
    'excluded_schematic_diagram_not_a_product_photo': dimension_diagram,
    'excluded_no_console_visible_screenshot_of_tv': no_console_visible,
    'candidates_for_visual_check_console_visible_color_unstated': generic_console_no_color_stated,
}

# --- 4. Note the duplicate/broken reference: the "Left angle... boxshot" alt reuses the White A1 asset ---
findings['note_on_duplicate_reference'] = (
    'The alt text "Left angle of the XBOX Series S with an XBOX wireless controller and XBOX '
    'boxshot" is attached to an <img> whose srcset points at the same asset id '
    '(bfb06f23-...-ed25d3a739b9.png, i.e. Hero-Gallery-0_A1, the 512GB White bundle image) as '
    'the confirmed-White gallery slide, with an empty src -- a template/markup artifact, not an '
    'independent image. Not counted as a separate candidate.'
)

(OUT / 'offline_dom_gallery_analysis.json').write_text(json.dumps(findings, indent=2, ensure_ascii=False), encoding='utf-8')
print('candidates for visual check:')
for r in findings['classification']['candidates_for_visual_check_console_visible_color_unstated']:
    print(' -', r['alt'], '|', r['src'])
print('hero_gallery conclusion:', findings['hero_gallery_carousel']['conclusion'][:200], '...')
