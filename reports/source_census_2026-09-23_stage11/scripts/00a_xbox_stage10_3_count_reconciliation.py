"""Stage 11, part A -- offline correction addendum to Stage 10.3. Stage 10.3's
own artifacts are read-only and unmodified; this writes a NEW file in this
stage's own directory that reconciles the "17" rejected-image count against
the 6 listed classification categories (21 total classified), and records
exact URLs + byte hashes + rejection reasons for the 2 visually-checked
candidates, using the bytes already fetched in Stage 10.3 (kept in the
session scratch dir, not re-fetched -- no new network request for this part).
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(r'A:\work\dev\product_cards_mvp')
STAGE10_3 = ROOT / 'reports/source_census_2026-09-23_stage10_3'
OUT = ROOT / 'reports/source_census_2026-09-23_stage11'
SCRATCH_IMAGES = Path(
    r'C:\Users\Julynce\AppData\Local\Temp\claude\a--work-dev-product-cards-mvp'
    r'\1741bb85-29db-47a4-97a9-ed84155ebc47\scratchpad\stage10_3_images'
)

gallery = json.loads((STAGE10_3 / 'offline_dom_gallery_analysis.json').read_text(encoding='utf-8'))
card = json.loads((STAGE10_3 / 'card.json').read_text(encoding='utf-8'))
phase2 = json.loads((STAGE10_3 / 'phase2_fetch_candidate_images.json').read_text(encoding='utf-8'))

classification = gallery['classification']
category_counts = {k: len(v) for k, v in classification.items()}
total_classified = sum(category_counts.values())

rejected_categories = [
    'rejected_confirmed_white_by_alt_text_or_shared_bundle_id',
    'rejected_environmental_illustration_not_color_evidence',
    'candidates_for_visual_check_console_visible_color_unstated',  # both ended up rejected after visual check
]
excluded_categories = [
    'rejected_different_product_refurbished_listing',
    'excluded_schematic_diagram_not_a_product_photo',
    'excluded_no_console_visible_screenshot_of_tv',
]
rejected_sum = sum(category_counts[k] for k in rejected_categories)
excluded_sum = sum(category_counts[k] for k in excluded_categories)

reconciliation = {
    'stage10_3_images_rejected_count_field': card['images_rejected_count'],
    'category_counts': category_counts,
    'total_elements_classified_across_all_6_categories': total_classified,
    'breakdown': {
        'counted_in_the_17_rejected_figure': {
            'categories': rejected_categories,
            'sum': rejected_sum,
            'note': (
                'The card.json "images_rejected_count": 17 equals '
                f'{category_counts[rejected_categories[0]]} (white bundle) + '
                f'{category_counts[rejected_categories[1]]} (Carbon-Aware) + '
                f'{category_counts[rejected_categories[2]]} (the 2 visually-checked candidates, '
                'both rejected after inspection) = 17. This matches len(images_rejected_with_evidence) '
                'in card.json exactly.'
            ),
        },
        'NOT_counted_in_the_17_kept_as_a_separate_excluded_list': {
            'categories': excluded_categories,
            'sum': excluded_sum,
            'note': (
                'card.json keeps these 4 elements in a separate field '
                '("images_excluded_not_treated_as_evidence_either_way") precisely because they '
                'were never fetched or evaluated as color evidence one way or the other (a '
                'different product listing, a technical schematic, and 2 TV-screenshot '
                'elements with no console visible). They were deliberately NOT added to the '
                'rejected-with-evidence count, to avoid inflating a "rejected" tally with items '
                'that were never candidates for confirmation in the first place.'
            ),
        },
    },
    'reconciliation_result': (
        f'17 (rejected) + {excluded_sum} (excluded, not evidence either way) = '
        f'{rejected_sum + excluded_sum} total live <img> elements classified from the two known '
        'Xbox asset CDN hosts. No overlap between the two buckets -- every element appears in '
        'exactly one category. Stage 10.3\'s report.md correctly used "17" for the rejected-'
        'with-evidence count and separately listed the 4 excluded elements; this addendum makes '
        'the arithmetic explicit for anyone auditing the count.'
    ),
    'stage10_3_conclusion_unchanged': True,
    'stage10_3_conclusion_unchanged_reason': (
        'This is a bookkeeping clarification only. No new evidence was gathered about any '
        'image\'s color or relevance -- Stage 10.3\'s verdict (0 images accepted for the Carbon '
        'Black 1TB variant) stands exactly as recorded.'
    ),
}

# --- Byte hashes for the two visually-checked candidates, using bytes already fetched
# in Stage 10.3 (kept in this session's scratch dir, not re-fetched) ---
visual_candidates = []
url_to_scratch_file = {
    'https://cms-assets.xboxservices.com/assets/4a/ac/4aac334d-a7f7-4bc3-93a8-58151dd17851.jpg?n=Xbox-Series-S_Super-Hero-1400_Complete-Control_1920x1400_01.jpg':
        'Xbox-Series-S_Super-Hero-1400_Complete-Control_1920x1400_01.jpg',
    'https://assets.xboxservices.com/assets/87/90/879088f1-3b89-46a6-9d38-44694d5e924c.jpg?n=XBX_L-StorageExpansion-D.jpg':
        'XBX_L-StorageExpansion-D.jpg',
}
rejection_reasons = {
    r['url']: r for r in card['images_rejected_with_evidence'] if r['reason'] == 'visually_confirmed_white_not_carbon_black'
}

for url, fname in url_to_scratch_file.items():
    fpath = SCRATCH_IMAGES / fname
    data = fpath.read_bytes()
    sha256 = hashlib.sha256(data).hexdigest()
    visual_candidates.append({
        'url': url,
        'alt_text': phase2['results'][url]['alt_text'],
        'byte_count': len(data),
        'sha256': sha256,
        'declared_total_bytes_at_fetch_time': phase2['results'][url]['declared_total_bytes'],
        'byte_count_matches_declared_total': len(data) == phase2['results'][url]['declared_total_bytes'],
        'rejection_reason': rejection_reasons[url]['reason'],
        'rejection_evidence': rejection_reasons[url]['evidence'],
        'bytes_source': 'session scratch dir copy from Stage 10.3\'s original fetch; no new network request this stage',
    })

output = {
    'reconciliation': reconciliation,
    'visually_checked_candidates_hashed': visual_candidates,
}

(OUT / 'xbox_stage10_3_addendum.json').write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding='utf-8')
print(json.dumps(reconciliation['breakdown'], indent=2, ensure_ascii=False))
for c in visual_candidates:
    print(c['url'], c['sha256'], c['byte_count_matches_declared_total'])
