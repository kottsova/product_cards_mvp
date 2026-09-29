"""Stage 9.1 -- fully offline. Inspect the catalog schema and both DualSense
Cosmic Red rows field-by-field, and classify which fields could plausibly be
manufacturer/regional-variant evidence versus marketplace-listing metadata.
No network access in this script."""
import json
from pathlib import Path

ROOT = Path(r'A:\work\dev\product_cards_mvp')
OUT = ROOT / 'reports/source_census_2026-09-22_stage9_1'

rows = json.loads((OUT / 'raw/catalog_rows_full.json').read_text(encoding='utf-8'))
header = json.loads((OUT / 'raw/header.json').read_text(encoding='utf-8'))

row_j = next(r for r in rows if r['Артикул продавца'] == 'CFI-ZCT1J 02')
row_w = next(r for r in rows if r['Артикул продавца'] == 'CFI-ZCT1W_cosmic_red')

analysis = {
    'schema_version': 'stage9_1_offline_row_analysis.v1',
    'method': 'openpyxl read_only=True, data_only=True on data/catalog_2026-09-21_filtered.xlsx, sheet "Товары" -- 0 network requests',
    'catalog_schema_full': {
        'total_columns': len(header),
        'column_names': header,
        'dedicated_manufacturer_or_region_code_field_exists': False,
        'schema_note': (
            'The catalog has exactly 8 columns: Бренд, Категория, Артикул продавца, Артикулы WB, '
            'Наименование, Альтернативные наименования, ТНВЭД, Повторов в выгрузках. There is no column '
            'named or semantically dedicated to a manufacturer/factory code, region code, or product-variant '
            'code. "Артикул продавца" (seller article) is a free-text field the SELLER fills in -- it is not '
            'sourced from or verified against any manufacturer registry by catalog construction.'
        ),
    },
    'row_CFI-ZCT1J_02': row_j,
    'row_CFI-ZCT1W_cosmic_red': row_w,
    'field_by_field_comparison': [
        {
            'field': 'Бренд',
            'row_j': row_j['Бренд'], 'row_w': row_w['Бренд'],
            'differs': row_j['Бренд'] != row_w['Бренд'],
            'is_variant_evidence': False,
            'reasoning': 'Identical ("Playstation") -- not a source of distinction.',
        },
        {
            'field': 'Категория',
            'row_j': row_j['Категория'], 'row_w': row_w['Категория'],
            'differs': row_j['Категория'] != row_w['Категория'],
            'is_variant_evidence': False,
            'reasoning': 'Identical ("Геймпады") -- not a source of distinction.',
        },
        {
            'field': 'Наименование',
            'row_j': row_j['Наименование'], 'row_w': row_w['Наименование'],
            'differs': row_j['Наименование'] != row_w['Наименование'],
            'is_variant_evidence': False,
            'reasoning': (
                'Text differs ("Геймпад DualSense для PS5 Cosmic Red" vs "Беспроводной геймпад DualSense '
                'Cosmic Red"), but both name the identical product line (DualSense) and the identical color '
                '(Cosmic Red); the difference is phrasing/emphasis ("for PS5" vs "wireless"), not a distinct '
                'descriptor (no memory size, no region, no edition, no bundle content mentioned in either). '
                'Both descriptions are consistent with the SAME confirmed official variant.'
            ),
        },
        {
            'field': 'Артикул продавца (seller article)',
            'row_j': row_j['Артикул продавца'], 'row_w': row_w['Артикул продавца'],
            'differs': True,
            'is_variant_evidence': 'unverified',
            'reasoning': (
                'Strings differ (CFI-ZCT1J 02 vs CFI-ZCT1W_cosmic_red). This LOOKS like it could follow '
                "Sony's own CFI-ZCT1x code pattern, but per explicit instruction this difference alone must "
                'NOT be treated as proof of a genuine factory/regional variant distinction -- it is a '
                'seller-entered field, not verified against any manufacturer registry in the catalog itself, '
                'and no official PlayStation source checked in this or prior stages displays either code '
                '(see known_routes_review.json). Status: unverified, neither confirmed same nor confirmed different.'
            ),
        },
        {
            'field': 'Артикулы WB (Wildberries marketplace listing numbers)',
            'row_j': row_j['Артикулы WB'], 'row_w': row_w['Артикулы WB'],
            'differs': True,
            'is_variant_evidence': False,
            'reasoning': (
                'Different WB listing numbers are EXPECTED for any two independent marketplace listings '
                'regardless of whether the underlying physical product is identical or different -- this is a '
                'marketplace-listing-instance identifier (directly analogous to Stage 9\'s finding that the '
                "official page's own microdata `sku` (1000050734) was PS Direct's internal webstore ID, not a "
                'manufacturer code). Not usable as product-identity evidence.'
            ),
        },
        {
            'field': 'ТНВЭД (customs HS code)',
            'row_j': row_j['ТНВЭД'], 'row_w': row_w['ТНВЭД'],
            'differs': True,
            'is_variant_evidence': False,
            'reasoning': (
                'Row J is null (not filled in), row W is "9504500009". This is presence-vs-absence, not two '
                'conflicting values for the same classification -- the simplest explanation is an incomplete '
                'seller data entry for row J, not a genuine customs-classification conflict. A customs HS code '
                'also classifies a broad product category (game controllers), not a specific factory/regional '
                'SKU, so even a populated value would not by itself prove a manufacturing-variant difference.'
            ),
        },
        {
            'field': 'Повторов в выгрузках (repeat count in scrape exports)',
            'row_j': row_j['Повторов в выгрузках'], 'row_w': row_w['Повторов в выгрузках'],
            'differs': True,
            'is_variant_evidence': False,
            'reasoning': 'Scrape/export bookkeeping metadata, unrelated to product identity.',
        },
        {
            'field': 'Альтернативные наименования',
            'row_j': row_j['Альтернативные наименования'], 'row_w': row_w['Альтернативные наименования'],
            'differs': False,
            'is_variant_evidence': False,
            'reasoning': 'Both null -- no additional naming evidence available.',
        },
    ],
    'conclusion': (
        'No catalog field constitutes verified manufacturer/regional-variant evidence. The only field that '
        'differs in a way that COULD plausibly reflect a genuine factory/regional distinction is the '
        'seller-assigned article code -- and per explicit instruction, that difference cannot be used alone to '
        'conclude the rows describe different variants. Every other differing field (WB numbers, TNVED '
        'presence, repeat count) is marketplace-listing metadata, not manufacturer-level identification. Both '
        'rows\' own descriptive names are consistent with the identical confirmed product (DualSense Wireless '
        'Controller, Cosmic Red). No rows were merged or deleted; both are carried forward as separate catalog '
        'records with their own evidence.'
    ),
}

(OUT / 'offline_row_analysis.json').write_text(json.dumps(analysis, indent=2, ensure_ascii=False), encoding='utf-8')
print('wrote offline_row_analysis.json')
