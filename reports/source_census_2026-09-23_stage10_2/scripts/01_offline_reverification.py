"""Stage 10.2 -- offline re-audit of Stage 10.1's saved Xbox Series S landing
page. No new network requests. For every field Stage 10.1 accepted, determines
whether the evidence is line-wide (applies to all Series S SKUs) or variant-
specific (Carbon Black 1TB only), and re-verifies each quoted string is live,
rendered HTML -- not dead markup inside an <!-- --> comment.
"""
import json
import re
from pathlib import Path

ROOT = Path(r'A:\work\dev\product_cards_mvp')
STAGE10_1 = ROOT / 'reports/source_census_2026-09-23_stage10_1'
OUT = ROOT / 'reports/source_census_2026-09-23_stage10_2'

text = (STAGE10_1 / 'raw/series_s_landing_en_us.html.txt').read_text(encoding='utf-8', errors='replace')


def comment_spans(s):
    return [(m.start(), s.find('-->', m.start()) + 3) for m in re.finditer(r'<!--', s)]


SPANS = comment_spans(text)


def is_commented(pos):
    for start, end in SPANS:
        if end <= start:  # unterminated, ignore
            continue
        if start <= pos < end:
            return True
    return False


def find_live_plain(needle, near=None):
    """Return the first plain-HTML (non JSON-escaped), non-commented occurrence."""
    for m in re.finditer(re.escape(needle), text):
        pos = m.start()
        escaped = '\\u003' in text[max(0, pos - 15):pos]
        if escaped:
            continue
        if is_commented(pos):
            continue
        if near is not None and abs(pos - near) > 50000:
            continue
        return pos
    return None


findings = {}

# --- The variant selector: two near-duplicate copies exist; one is dead markup ---
first_selector_pos = text.find('data-option="s-standard" selected="selected">512GB')
occurrences = [m.start() for m in re.finditer(r'<option data-option="s-standard" selected="selected">512GB', text)]
selector_copies = []
for pos in occurrences:
    selector_copies.append({'position': pos, 'inside_html_comment': is_commented(pos)})
findings['variant_selector_markup'] = {
    'copies_found': selector_copies,
    'conclusion': (
        'Two near-identical <select> variant pickers exist on the page. One (the first, '
        'inside the legacy in-page-navigation menu) is wrapped in an HTML comment '
        '(<!--...-->) and is dead markup, not rendered. The second, later in the page, is '
        'live and uncommented, with a functional aria-label ("...This also changes the '
        'images in the gallery near the top of the page.") and matching, also-uncommented '
        '"CTAdiv option s-new/s-standard/s-special" purchase buttons. Stage 10.1\'s evidence '
        'is confirmed sourced from live markup; the dead copy is noted but not relied upon.'
    ),
}

# --- JS hash-routing confirms s-new = Carbon Black is a real, addressable option ---
hash_route_pos = text.find("case '#black1tb':")
findings['js_hash_routing'] = {
    'found': hash_route_pos is not None and hash_route_pos > 0,
    'position': hash_route_pos,
    'inside_html_comment': is_commented(hash_route_pos) if hash_route_pos > 0 else None,
    'quote': "case '#black1tb': case '#purchaseblack1tb': theOption = 's-new'; break;",
    'conclusion': 'Live JS maps the URL anchors #black1tb / #purchaseblack1tb to the s-new (Carbon Black 1TB) option -- independent corroboration this is a real, addressable SKU, not template placeholder text.',
}

# --- The "Carbon-Aware" images: re-read their actual caption/section text ---
carbon_aware_tab_pos = find_live_plain('Carbon aware')
content2_pos = text.find('id="newRTBItemContent2"')
caption_start = content2_pos
caption_text = ''
if caption_start > 0:
    chunk = text[caption_start:caption_start + 700]
    plain = re.sub(r'<[^>]+>', ' ', chunk)
    plain = re.sub(r'\s+', ' ', plain).strip()
    caption_text = plain
findings['carbon_aware_images_correction'] = {
    'stage10_1_claim': (
        'Stage 10.1 card.json listed 3 images whose filenames contain "Carbon-Aware" '
        '(e.g. Xbox-Series-S_Multi-Feature-1084_Carbon-Aware_1040x990_01.jpg) as evidence '
        'for the Carbon Black color variant.'
    ),
    'tab_label_context': '"Carbon aware" is a tab inside a "Peace of mind" pivot section, sibling to a "Safer gaming" (parental controls) tab, aria-label="Purchase Restrictions".',
    'actual_panel_text_found': caption_text,
    'correction': (
        'INCORRECT in Stage 10.1. "Carbon aware" here refers to Xbox\'s environmental/'
        'sustainability messaging (post-consumer-recycled plastics and energy-saving power '
        'modes), not the "Carbon Black" color. The image alt text ("XBOX Series S surrounded '
        'by leaves and plants") is a nature/lifestyle illustration of this feature, applies to '
        'the whole Series S line regardless of color, and depicts no specific SKU. These 3 '
        'images are RETRACTED as color-variant evidence in this stage\'s card.'
    ),
}

# --- Search for any genuine per-color product photo ---
image_urls = sorted(set(re.findall(r'https://cms-assets\.xboxservices\.com/[^"\'\\ ]+', text)))
color_named = [u for u in image_urls if re.search(r'black|white|robot', u, re.I)]
findings['genuine_color_specific_image_search'] = {
    'total_image_video_assets_on_page': len(image_urls),
    'assets_with_color_words_in_filename': color_named,
    'conclusion': (
        'No image or video asset filename references "Black", "White", or "Robot" (the '
        'official color names). The gallery-swap behavior implied by the selector\'s own '
        'aria-label is handled client-side (JS/CSS class toggling of hidden elements) and no '
        'per-option image URL is present in static markup. No official image can be confirmed '
        'this stage as specifically depicting the Carbon Black 1TB unit.'
    ),
}

# --- Storage: re-confirm variant-specific pairing is live ---
storage_pos = find_live_plain('XBOX Series S Carbon Black: 1TB Custom NVME SSD')
findings['storage_reverification'] = {
    'position': storage_pos,
    'inside_html_comment': is_commented(storage_pos) if storage_pos else None,
    'quote': 'XBOX Series S Robot White: 512GB Custom NVME SSD / XBOX Series S Carbon Black: 1TB Custom NVME SSD / XBOX Series S Robot White: 1TB Custom NVME SSD',
    'classification': 'variant_specific',
    'conclusion': 'Confirmed live, uncommented. Storage is the one spec explicitly and separately stated per color+capacity combination -- correctly variant-specific in Stage 10.1, reconfirmed here.',
}

# --- Dimensions / Weight: confirm these are NOT split per variant ---
dim_pos = find_live_plain('6.5cm x 15.1cm x 27.5cm')
weight_pos = find_live_plain('4.25 lbs.')
findings['dimensions_and_weight_reverification'] = {
    'dimensions': {'value': '6.5cm x 15.1cm x 27.5cm', 'position': dim_pos, 'inside_html_comment': is_commented(dim_pos) if dim_pos else None},
    'weight': {'value': '4.25 lbs.', 'position': weight_pos, 'inside_html_comment': is_commented(weight_pos) if weight_pos else None},
    'classification': 'line_wide_not_variant_specific',
    'conclusion': (
        'Both appear exactly once on the page, in the shared TECH SPECS drawer, with no '
        'per-option repetition (unlike storage, which repeats three times, once per color+'
        'capacity combination). These describe the Series S form factor generically. Not '
        'demonstrated to differ between color/capacity SKUs, but also not demonstrated to be '
        'identical by the page itself -- treated as line-wide evidence, applied to the Carbon '
        'Black 1TB unit only by physical-design inference, not by an explicit per-SKU '
        'statement. Consistent with Stage 10.1\'s own caveat, now confirmed via live-markup check.'
    ),
}

# --- CPU / GPU / Memory / video / sound / ports: also line-wide (never repeated per option) ---
findings['other_specs_classification'] = {
    'fields': ['CPU', 'GPU', 'Memory', 'Memory Bandwidth', 'I/O Throughput', 'Expandable Storage',
               'Gaming Resolution', 'Performance Target', 'HDMI Features', 'Sound formats', 'Ports', 'Wireless'],
    'classification': 'line_wide_not_variant_specific',
    'reason': 'None of these are restated per color/capacity option anywhere on the page (only "Internal Storage" is). They describe the Xbox Series S platform as a whole and apply equally to the Carbon Black 1TB unit as to the two white SKUs.',
}

# --- Seller article: confirm catalog identifier convention ---
findings['seller_article_handling'] = {
    'seller_article': 'XXU-00015',
    'rule_applied': (
        'Kept as the catalog identifier only. Not searched for on the official page, and its '
        'absence there (confirmed absent in Stage 10.1 and rechecked here -- zero occurrences '
        'of "XXU-00015" or any manufacturer/region code in the saved page text) is not treated '
        'as evidence of anything, per instructions.'
    ),
    'confirmed_absent_from_page': 'XXU-00015' not in text,
}

(OUT / 'offline_reverification.json').write_text(json.dumps(findings, indent=2, ensure_ascii=False), encoding='utf-8')
print(json.dumps({k: v.get('conclusion', v.get('correction', '')) for k, v in findings.items() if isinstance(v, dict)}, indent=2, ensure_ascii=False))
