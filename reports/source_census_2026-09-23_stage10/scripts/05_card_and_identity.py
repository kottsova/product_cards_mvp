"""Stage 10 — separated identity statuses, export-readiness card, field-level evidence table."""
import json
from pathlib import Path

ROOT = Path(r'A:\work\dev\product_cards_mvp')
OUT = ROOT / 'reports/source_census_2026-09-23_stage10'

offline = json.loads((OUT / 'offline_row_analysis.json').read_text(encoding='utf-8'))
routes = json.loads((OUT / 'known_routes_review.json').read_text(encoding='utf-8'))
probe = json.loads((OUT / 'bounded_probe_result.json').read_text(encoding='utf-8'))
row = offline['selected_row']

identity_statuses = {
    'brand_entity_identity': {
        'status': 'confirmed_official',
        'evidence': (
            'https://support.microsoft.com/en-us/all-products-list (HTTP 200, direct_access, '
            'fetched this stage) is Microsoft\'s own official support portal and itself links '
            'to "Xbox" (support.xbox.com), "Shop XBOX" and "XBOX games" as Microsoft\'s own '
            'product family via its own global navigation.'
        ),
        'confirms': 'Microsoft is a real corporate entity with Xbox as a self-declared first-party product line.',
        'does_not_confirm': 'Any specific Xbox model, variant, specification, image, or manual.',
    },
    'product_line_identity_xbox_series_s': {
        'status': 'not_confirmed',
        'reason': (
            'Zero occurrences of "Series S" or "Xbox Series S" in the fetched, bounded content '
            'of https://support.microsoft.com/en-us/all-products-list (108,197 bytes read, not '
            'truncated). The candidate product-page hosts that would carry this (www.xbox.com, '
            'support.xbox.com) were discovered as links on that official page but are off-host '
            'relative to the pre-declared allowlist and were not requested this stage.'
        ),
    },
    'variant_identity_carbon_1tb': {
        'status': 'not_confirmed',
        'reason': 'No official page reached this stage mentions capacity or color/finish for this or any Xbox Series S SKU.',
    },
    'catalog_row_to_official_variant_linkage': {
        'status': 'not_applicable_yet',
        'reason': 'Cannot be assessed before the variant itself is officially confirmed (see Stage 9.1 methodology: linkage is a separate, later question from variant confirmation, and both require the variant step first).',
    },
    'specifications': {'status': 'not_found', 'reason': 'No product page reached.'},
    'images': {'status': 'not_found', 'reason': 'No product page reached; no image-fetch step was attempted.'},
    'instruction_manual': {
        'status': 'not_searched',
        'reason': (
            'The Stage 8.6 bounded-document-verification mechanism (fetch_document_bounded) '
            'was not invoked because no candidate PDF URL was discovered within the allowed '
            'host and budget this stage.'
        ),
    },
}

exportable_fields_with_evidence = [
    {
        'field': 'Бренд (Microsoft)',
        'value': row['Бренд'],
        'evidence': 'Catalog cell, cross-checked against the officially-confirmed corporate entity at support.microsoft.com (fetched this stage, HTTP 200).',
        'caveat': 'Confirms the brand exists and operates Xbox as a product line; does not itself confirm this catalog row is genuinely a Microsoft product (that link is catalog-only, see catalog_row_to_official_variant_linkage).',
    },
    {
        'field': 'Категория (Игровые консоли) — informational only',
        'value': row['Категория'],
        'evidence': 'Catalog cell only.',
        'caveat': 'Not independently verified against any official taxonomy.',
    },
    {
        'field': 'Наименование / Артикул продавца (raw catalog identity)',
        'value': f"{row['Наименование']} / {row['Артикул продавца']}",
        'evidence': 'Catalog cells only.',
        'caveat': 'Unverified seller-entered text; per project rule, absence of external conflict is not proof of a correct match.',
    },
]

five_point_criterion = {
    'criterion_1_brand_model_confirmed_by_official_source': {
        'pass': False,
        'detail': 'Brand confirmed; model (Xbox Series S) not confirmed by any fetched official content this stage.',
    },
    'criterion_2_catalog_row_linked_to_confirmed_variant': {
        'pass': False,
        'detail': 'Blocked upstream of Stage 9.1\'s equivalent question — there is no confirmed variant yet to link the row to.',
    },
    'criterion_3_official_matched_image_confirmed': {'pass': False, 'detail': 'No image obtained.'},
    'criterion_4_specifications_sufficient': {'pass': False, 'detail': 'No specifications obtained.'},
    'criterion_5_manual_confirmed_present_or_absence_noted': {
        'pass': False,
        'detail': 'Neither presence nor absence could be checked — no product/support page for this model was reached, so this is an open item, not a confirmed absence.',
    },
}

card = {
    'stage': 10,
    'scope': 'Microsoft/Xbox, catalog-first full cycle, single selected row',
    'selected_catalog_row': row,
    'identity_statuses': identity_statuses,
    'exportable_fields_with_evidence': exportable_fields_with_evidence,
    'five_point_export_readiness_criterion': five_point_criterion,
    'export_readiness': 'not_ready',
    'export_readiness_reason': (
        'Fails criterion 1 already (model/variant not officially confirmed), which is earlier '
        'in the pipeline than the gaps found for previously-processed products (Samsung '
        'microwave reached ready_with_minor_gaps; PlayStation DualSense reached not_ready but '
        'only for missing numeric specs). The blocker here is structural: this project\'s '
        'official-domain registry (official_domains.v1.json) has no verified product-page host '
        'for Microsoft/Xbox yet, only a support-role host (support.microsoft.com) that carries '
        'no product-specific content, only navigation to off-registry hosts (www.xbox.com, '
        'support.xbox.com).'
    ),
    'gaps': [
        'No official_domains.v1.json entry at all for Microsoft/Xbox, and the one confirmed route on file anywhere (support.microsoft.com) is support-role only, with no manufacturer/retailer-role host to carry commercial product-page content.',
        'Model line "Xbox Series S" not confirmed by any fetched official content.',
        'Variant (1TB, Carbon finish) not confirmed.',
        'Specifications: none found.',
        'Images: none found.',
        'Instruction manual: not searched (no reachable product/support page for this model).',
    ],
    'discovered_but_unconfirmed_leads_for_a_future_stage': probe['off_host_links_seen_but_not_followed'],
    'discovered_leads_note': (
        'These are literal hrefs read from an official Microsoft page, not guessed — but they '
        'are off the pre-declared allowlist and have no ownership_evidence recorded in '
        'official_domains.v1.json. Per this stage\'s rules they were recorded, not followed. '
        'A future stage could add www.xbox.com / support.xbox.com to official_domains.v1.json '
        'following the same evidence-gathering process already used for the 17 existing '
        'entries (e.g. LG), then re-run a bounded discovery.'
    ),
}

(OUT / 'card.json').write_text(json.dumps(card, indent=2, ensure_ascii=False), encoding='utf-8')
print('export_readiness:', card['export_readiness'])
