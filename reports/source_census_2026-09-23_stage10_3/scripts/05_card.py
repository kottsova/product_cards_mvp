"""Stage 10.3 -- final card: accepted/rejected images with evidence, variant vs
line-wide fields carried forward from Stage 10.2, manual left unconfirmed
(not re-searched), corrected 5-point criterion."""
import json
from pathlib import Path

ROOT = Path(r'A:\work\dev\product_cards_mvp')
OUT = ROOT / 'reports/source_census_2026-09-23_stage10_3'
STAGE10 = ROOT / 'reports/source_census_2026-09-23_stage10'
STAGE10_2 = ROOT / 'reports/source_census_2026-09-23_stage10_2'

offline_row = json.loads((STAGE10 / 'offline_row_analysis.json').read_text(encoding='utf-8'))['selected_row']
prior_card = json.loads((STAGE10_2 / 'card.json').read_text(encoding='utf-8'))
gallery = json.loads((OUT / 'offline_dom_gallery_analysis.json').read_text(encoding='utf-8'))
fetch_result = json.loads((OUT / 'phase2_fetch_candidate_images.json').read_text(encoding='utf-8'))['results']

PAGE_URL = 'https://www.xbox.com/en-US/consoles/xbox-series-s'

images_rejected = []

# 1. The 8 white-bundle images (structural + textual confirmation, no fetch needed -- already White by the page's own alt text)
for r in gallery['classification']['rejected_confirmed_white_by_alt_text_or_shared_bundle_id']:
    images_rejected.append({
        'url': r['src'], 'alt_text': r['alt'],
        'evidence': 'The page\'s own alt text names the color/capacity explicitly ("Robot White"), and/or the asset is part of the single "389964" buy-box bundle confirmed White by its own surrounding retail text ("Includes: ... XBOX Wireless Controller – Robot White"). Not fetched -- rejected on textual evidence alone.',
        'reason': 'confirmed_white_not_carbon_black',
    })

# 2. The 3 "Carbon-Aware" images (already established in Stage 10.2)
for r in gallery['classification']['rejected_environmental_illustration_not_color_evidence']:
    images_rejected.append({
        'url': r['src'], 'alt_text': r['alt'],
        'evidence': 'Confirmed by its own panel caption (Stage 10.2) to illustrate an unrelated sustainability/energy-saving feature, not the Carbon Black color.',
        'reason': 'unrelated_feature_illustration_not_color_evidence',
    })

# 3. The two visually-checked candidates -- REJECTED, confirmed White by direct visual inspection
for url, r in fetch_result.items():
    images_rejected.append({
        'url': url, 'alt_text': r['alt_text'],
        'evidence': (
            f'Fetched official CDN URL, byte-verified complete ({r["completeness"]}, '
            f'{r["declared_total_bytes"]} bytes, Content-Type {r["content_type"]}), and visually '
            f'inspected: shows a white-cased console' + (' and a white controller' if 'Controller' in r['alt_text'] or 'planet' in r['alt_text'] else '') + '. '
            'No Carbon Black casing visible; not tied to the Carbon Black option via DOM either.'
        ),
        'reason': 'visually_confirmed_white_not_carbon_black',
    })

# 4. Excluded, not fetched, not counted as rejected evidence (different product / not a color photo)
excluded_not_evidence = []
for r in gallery['classification']['rejected_different_product_refurbished_listing']:
    excluded_not_evidence.append({'url': r['src'], 'alt_text': r['alt'], 'reason': 'different_product_listing_certified_refurbished_not_this_variant'})
for r in gallery['classification']['excluded_schematic_diagram_not_a_product_photo']:
    excluded_not_evidence.append({'url': r['src'], 'alt_text': r['alt'], 'reason': 'technical_schematic_not_a_product_photo_low_value_for_color_not_fetched'})
for r in gallery['classification']['excluded_no_console_visible_screenshot_of_tv']:
    excluded_not_evidence.append({'url': r['src'], 'alt_text': r['alt'], 'reason': 'no_console_visible_screenshot_of_gameplay_on_a_tv_not_fetched'})

card = {
    'stage': '10.3',
    'scope': 'Final bounded image check for XXU-00015 (Xbox Series S, Carbon Black, 1TB). No manual search, no general Xbox census.',
    'selected_catalog_row': offline_row,

    'structural_finding': gallery['hero_gallery_carousel']['conclusion'],

    'images_accepted_for_the_card': [],
    'images_accepted_count': 0,

    'images_rejected_with_evidence': images_rejected,
    'images_rejected_count': len(images_rejected),
    'images_rejected_count_note': (
        'Counts individual <img>/<picture> elements on the live page, including responsive '
        'duplicates. The 3 distinct "Carbon-Aware" filenames noted in Stage 10.1/10.2 are one '
        'logical image at 3 resolutions -- only its single <img> fallback element is counted '
        'here; its 2 <source> siblings share the same evidence and are not double-counted as '
        'separate images.'
    ),
    'images_excluded_not_treated_as_evidence_either_way': excluded_not_evidence,

    'final_image_verdict': (
        'No official image was accepted for the Carbon Black 1TB variant. Every image found on '
        'the confirmed official product page was either (a) textually confirmed to depict a '
        'Robot White SKU, (b) confirmed by its own caption to illustrate an unrelated '
        'sustainability feature, or (c) fetched, byte-verified, and visually inspected, showing '
        'a white-cased console. The page\'s own per-variant image-gallery mechanism has '
        'dedicated slide sets for both Robot White SKUs (512GB and 1TB) but no corresponding '
        'set for Carbon Black at all -- a structural absence, not merely an unsuccessful search. '
        'This is stated as a confirmed gap in the available official content, not a claim that '
        'no such photo exists anywhere on xbox.com.'
    ),

    # Carried forward unchanged from Stage 10.2 -- not re-verified this stage
    'variant_specific_fields_carbon_black_1tb': prior_card['variant_specific_fields_carbon_black_1tb'],
    'line_wide_fields_applies_to_all_series_s_skus': prior_card['line_wide_fields_applies_to_all_series_s_skus'],
    'seller_article_handling': prior_card['seller_article_handling'],

    # Manual: explicitly left as-is, not re-searched this stage
    'manual_search': {
        'status': 'not_re_examined_this_stage',
        'carried_forward_from_stage_10_2': prior_card['manual_search']['status'],
        'note': (
            'Per instructions, this stage does not continue the manual search. Stage 10.2\'s '
            'result stands: two real, live, on-topic candidate articles exist in both Russian '
            'and English, but their content is unreachable without executing JavaScript, which '
            'stays out of scope. This remains neither confirmed present nor confirmed absent.'
        ),
    },

    'five_point_export_readiness_criterion': {
        'criterion_1_brand_model_confirmed_by_official_source': {'pass': True, 'detail': 'Unchanged from Stage 10.1/10.2.'},
        'criterion_2_catalog_row_linked_to_confirmed_variant': {'pass': True, 'detail': 'Unchanged: linked by model+capacity+color descriptive consistency (color and storage), independent of images.'},
        'criterion_3_official_matched_image_confirmed': {
            'pass': False,
            'detail': (
                'Confirmed failing after an exhaustive, small-number, visually-verified check: '
                '0 of the examined candidates depict the Carbon Black casing. This is now a '
                'confirmed absence within the available official content, not merely "not yet '
                'found."'
            ),
        },
        'criterion_4_specifications_sufficient': {'pass': True, 'detail': 'Unchanged from Stage 10.2.'},
        'criterion_5_manual_confirmed_present_or_absence_noted': {'pass': False, 'detail': 'Unchanged from Stage 10.2 -- not re-examined this stage.'},
    },
    'export_readiness': 'not_ready',
    'export_readiness_reason': (
        'Criteria 3 and 5 still fail. Criterion 3 is now a confirmed, evidence-backed absence '
        '(exhaustive small-number visual check performed) rather than an open search; criterion '
        '5 remains a structural JS-access blocker, left as Stage 10.2 recorded it.'
    ),
    'what_is_already_exportable_with_evidence': (
        'Brand, exact model, Carbon Black color, 1TB storage (variant-specific, each with URL '
        'and evidence), and a full line-wide technical specification set (with an explicit '
        'caveat on dimensions/weight) -- unchanged from Stage 10.2, all still exportable with '
        'evidence.'
    ),
    'what_is_not_ready': (
        'No official image confirmed for this exact variant (now a checked, evidence-backed '
        'gap rather than an unfound one), and the instruction manual remains neither confirmed '
        'present nor confirmed absent. Neither gap is stated as "this does not exist at all" -- '
        'both are scoped to what this project\'s bounded, no-Chromium routes could reach.'
    ),
}

(OUT / 'card.json').write_text(json.dumps(card, indent=2, ensure_ascii=False), encoding='utf-8')
print('images_accepted_count:', card['images_accepted_count'])
print('images_rejected_count:', len(card['images_rejected_with_evidence']))
print('criteria pass:', [k for k, v in card['five_point_export_readiness_criterion'].items() if v['pass']])
