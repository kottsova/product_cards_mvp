"""Stage 11 -- offline catalog scan for HyperX, matched against Stage 8.1's
already-confirmed official Product page fixtures. No network requests.
"""
import json
from pathlib import Path

import openpyxl

ROOT = Path(r'A:\work\dev\product_cards_mvp')
OUT = ROOT / 'reports/source_census_2026-09-23_stage11'
CATALOG = ROOT / 'data/catalog_2026-09-21_filtered.xlsx'
STAGE8_1 = ROOT / 'reports/source_census_2026-09-22_stage8_1'

wb = openpyxl.load_workbook(CATALOG, data_only=True, read_only=True)
ws = wb['Товары']
rows = list(ws.iter_rows(min_row=1, values_only=True))
header = rows[0]

matches = []
for i, row in enumerate(rows[1:], start=2):
    hay = ' '.join(str(v) for v in row if v is not None)
    if 'hyperx' in hay.lower():
        matches.append({'row_number': i, **dict(zip(header, row))})

by_brand = {}
for m in matches:
    by_brand.setdefault(m['Бренд'], []).append(m)

# Stage 8.1's confirmed, live-fetched HyperX Product pages (hyperx.com, Shopify) -- read from
# its own supplemental_fetch_results.json, not re-derived.
supplemental = json.loads((STAGE8_1 / 'supplemental_fetch_results.json').read_text(encoding='utf-8'))['hyperx']
confirmed_pages = {
    'https://hyperx.com/products/hyperx-quadcast-2-s-usb-microphone': supplemental['picked_fixture'],
    'https://hyperx.com/products/hyperx-cloud-alpha-air-open-back-gaming-headset': supplemental['third_fixture'],
}

selected_row = next(m for m in by_brand['HYPERX'] if m['Артикул продавца'] == '9A273AA')

result = {
    'brand_separation': {
        'rule_applied': 'Brand taken from the catalog\'s own "Бренд" column. "HYPERX" (gaming peripherals: keyboards, mice, headsets, microphones, mousepads, webcam) is kept fully separate from "Kingston" (memory modules that merely use "HyperX" as a Kingston sub-brand/product-line name inside "Наименование", e.g. "Kingston HyperX Fury/Predator/Impact"). Kingston memory is a different official domain (kingston.com) with no confirmed fixture from Stage 8.1 and is out of scope. "HIPER" (a distinct, unrelated brand name seen elsewhere in this project\'s priority-brand lists) does not appear in the catalog at all under this search and was not merged in.',
        'HYPERX_row_count': len(by_brand.get('HYPERX', [])),
        'Kingston_hyperx_labeled_row_count': len(by_brand.get('Kingston', [])),
    },
    'stage8_1_confirmed_official_pages': confirmed_pages,
    'all_hyperx_brand_rows': by_brand.get('HYPERX', []),
    'selected_row': selected_row,
    'selection_reason': (
        'Row 6985 (seller article 9A273AA), "Микрофон для пк игровой QuadCast 2S Black", is an '
        'exact model+variant match to the Stage 8.1-confirmed, live-fetched official Product '
        'page https://hyperx.com/products/hyperx-quadcast-2-s-usb-microphone (fixture '
        '1dd3897450ff08ae7bde27d72cc20a93e140ee61652f79dd96799d271d331099.json, is_product_page: '
        'true, identity/specifications/media contracts all observed). The URL slug '
        '"quadcast-2-s" and the catalog\'s own name "QuadCast 2S" denote the same model line; '
        'the catalog additionally specifies the color variant "Black". The other confirmed '
        'Stage 8.1 page (Cloud Alpha Air headset) has no corresponding catalog row at all -- no '
        '"Cloud Alpha Air" model appears among the 53 HyperX-brand catalog rows -- so it is not '
        'usable for a catalog-first cycle this stage.'
    ),
    'other_microphone_rows_not_selected_and_why': [
        {'seller_article': '4P5E2AA', 'name': 'Микрофон для пк игровой DuoCast', 'why_not': 'different model line (DuoCast, not QuadCast), no confirmed fixture for this exact model'},
        {'seller_article': '4P5P7AA', 'name': 'Микрофон для пк игровой QuadCast S', 'why_not': '"QuadCast S" (first generation), not "QuadCast 2S" -- a different, older model; the confirmed fixture is specifically for the "2S" generation'},
        {'seller_article': '872V1AA', 'name': 'Микрофон для пк игровой QuadCast 2 Black', 'why_not': '"QuadCast 2" (no "S" suffix) is a distinct SKU/model from "QuadCast 2S" per HyperX\'s own naming; not the confirmed fixture\'s model'},
        {'seller_article': 'AR0A0AA', 'name': 'Микрофон для пк игровой SoloCast 2', 'why_not': 'different model line entirely (SoloCast, not QuadCast)'},
    ],
}

OUT.mkdir(parents=True, exist_ok=True)
(OUT / 'offline_catalog_and_fixture_match.json').write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
print('HYPERX rows:', len(by_brand.get('HYPERX', [])), '| Kingston rows:', len(by_brand.get('Kingston', [])))
print('selected:', selected_row)
