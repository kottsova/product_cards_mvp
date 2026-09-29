"""Stage 11.2 -- final card: full 14-item gallery, video+cover evidence,
spec table, text sections, root-cause fix, completeness check, gaps, and the
one field that needs user/dealer input."""
import json
from pathlib import Path

ROOT = Path(r'A:\work\dev\product_cards_mvp')
STAGE11 = ROOT / 'reports/source_census_2026-09-23_stage11'
OUT = ROOT / 'reports/source_census_2026-09-23_stage11_2'

root_cause = json.loads((OUT / 'offline_gallery_root_cause.json').read_text(encoding='utf-8'))
phase1 = json.loads((OUT / 'phase1_fresh_product_page_and_gallery_fix.json').read_text(encoding='utf-8'))
phase2 = json.loads((OUT / 'phase2_video_and_cover_check.json').read_text(encoding='utf-8'))
text_sections = json.loads((OUT / 'text_sections.json').read_text(encoding='utf-8'))
stage11_card = json.loads((STAGE11 / 'card.json').read_text(encoding='utf-8'))

PAGE_URL = 'https://hyperx.com/products/hyperx-quadcast-2-s-usb-microphone'

gallery_14 = phase1['gallery_items_fresh']
gallery_labeled = []
for g in gallery_14:
    slug = g['url'].rsplit('/', 1)[-1].split('?')[0]
    kind = 'annotated_feature_callout' if 'annotated' in slug else ('main_product_photo' if 'main_1' in slug else 'angle_photo')
    gallery_labeled.append({'media_id': g['media_id'], 'url': g['url'], 'filename': slug, 'kind': kind})

card = {
    'stage': '11.2',
    'scope': 'HyperX QuadCast 2S (9A273AA) only: gallery completeness fix, video+cover evidence, text sections.',

    'gallery_root_cause_and_fix': {
        'previous_result': '9 of 14 (Stage 11)',
        'root_cause': root_cause['root_cause']['why_they_were_missed'],
        'fix': root_cause['root_cause']['actual_dom_grouping'],
        'items_missed_before': root_cause['root_cause']['items_stage11_missed'],
    },
    'gallery_completeness_check': {
        'fresh_fetch_this_stage': phase1['corrected_gallery_completeness_check_fresh_page'],
        'stage11_snapshot_reread': phase1['corrected_gallery_completeness_check_stage11_snapshot'],
        'fresh_vs_saved_image_set_identical': phase1['comparison_to_stage11_snapshot']['gallery_urls_identical_set'],
    },
    'gallery_14_items': gallery_labeled,

    'video_evidence': {
        'user_provided_url': 'https://cdn.shopify.com/videos/c/o/v/b05b09498da44727be948864df7222ac.mp4',
        'dom_linkage_to_this_exact_page': root_cause['video_evidence']['conclusion'],
        'shares_page_template_id_with_gallery': root_cause['video_evidence']['shares_same_page_template_id_as_the_14_image_gallery'],
        'type_and_availability_check': {
            'method': 'bounded Range GET, first 64KB only -- not a full download',
            'http_status': phase2['video_check']['http_status'],
            'content_type': phase2['video_check']['content_type'],
            'is_valid_mp4_container_signature': phase2['video_check']['is_mp4_signature'],
            'declared_total_bytes': phase2['video_check']['declared_total_bytes'],
        },
        'not_attributed_to_another_product_because': (
            'The video is embedded via a literal <video><source> tag inside a <deferred-media> '
            'block whose data-media-id and enclosing <section id="shopify-section-..."> share '
            'the exact same Shopify section-template id family as the confirmed 14-image '
            'gallery on THIS page. The shared cdn.shopify.com hostname alone was NOT used as '
            'evidence -- the DOM containment was.'
        ),
    },
    'cover_image_evidence_separate_from_video': {
        'url': phase2['cover_check']['url'],
        'byte_integrity': 'complete' if phase2['cover_check'].get('byte_count_matches_declared_total') else 'unknown',
        'sha256': phase2['cover_check'].get('sha256'),
        'bytes': phase2['cover_check'].get('declared_total_bytes'),
        'visual_content_confirmed': (
            'Yes -- the cover image explicitly reads "HYPERX QUADCAST 2 S" and "GLOW UP." in '
            'large text, showing the same RGB-lit microphone, on a desk with a keyboard/mouse/'
            'headset, with the HyperX logo -- unambiguous product-specific marketing artwork, '
            'not a generic placeholder.'
        ),
    },

    'specifications_table_unchanged_from_stage11': stage11_card['exportable_fields_with_evidence'],
    'text_sections': [s for s in text_sections['sections'] if s['heading'] not in
                       ('Microphone Specifications', 'Connections and Features', 'Physical Specifications',
                        "What's Included In the Box", 'Warranty', 'Shipping and Returns')],
    'text_sections_note': (
        'The data-description block also repeats the spec table and adds a "Shipping and '
        'Returns" section (standard commerce boilerplate, not product-specific) -- excluded '
        'here since the spec table is already reported once, not duplicated.'
    ),

    'open_gaps': [
        'Manual (Quick Start Guide): confirmed physically included in the box (spec table, unchanged since Stage 11); no online PDF/document URL or its language confirmed anywhere on hyperx.com (product page, /pages/support, or this stage\'s re-check) -- unresolved, not claimed absent.',
        '7 of the 9 originally-checked images (angle_3 through angle_9) remain filename-matched/DOM-grouped but not individually byte-fetched+visually verified (only main_1 and angle_2 were, in Stage 11.1); the 5 annotated images are newly identified this stage but not yet individually fetched+visually verified either.',
    ],

    'field_needing_user_or_dealer_input': {
        'exact_product': 'HyperX QuadCast 2 S – USB Microphone, color Black, catalog seller article 9A273AA',
        'missing_field': 'Online/downloadable Quick Start Guide (instruction manual) document and its confirmed language',
        'official_pages_checked': [
            PAGE_URL + ' (full page, gallery, spec table, text sections, video -- no PDF/manual link anywhere)',
            'https://hyperx.com/pages/support (Stage 11 -- no PDF, no model-specific mention)',
        ],
        'what_is_specifically_needed': (
            'Either (a) a direct URL to an official or dealer-hosted PDF/web version of the '
            'QuadCast 2S Quick Start Guide, with its language, or (b) explicit confirmation to '
            'leave this field open (not searched further) rather than pursued indefinitely, or '
            '(c) if a dealer source is to be used, the exact dealer domain and confirmation that '
            'it is allowed for this brand/category -- note that the current allowlist (Sulpak) '
            'only covers a fixed LG home-appliance category set and does not cover HyperX or '
            'microphones, so no dealer fallback applies here without a new, explicit decision.'
        ),
    },
    'dealer_fallback_status': (
        'Not invoked this stage. No specific dealer domain has been determined for HyperX '
        'peripherals, and Sulpak\'s existing allowlist is scoped exclusively to LG home '
        'appliances (washers/dryers, refrigerators, vacuums, microwaves) -- it does not apply '
        'to this brand or category. Mechta remains excluded per standing instructions. No new '
        'dealer was added to the production registry.'
    ),
}

(OUT / 'card.json').write_text(json.dumps(card, indent=2, ensure_ascii=False), encoding='utf-8')
print('gallery items:', len(card['gallery_14_items']))
print('video valid mp4:', card['video_evidence']['type_and_availability_check']['is_valid_mp4_container_signature'])
