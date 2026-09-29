"""Stage 10 — offline catalog row analysis for Xbox/Microsoft, no network requests."""
import json
from pathlib import Path

import openpyxl

ROOT = Path(r'A:\work\dev\product_cards_mvp')
OUT = ROOT / 'reports/source_census_2026-09-23_stage10'
CATALOG = ROOT / 'data/catalog_2026-09-21_filtered.xlsx'

wb = openpyxl.load_workbook(CATALOG, data_only=True, read_only=True)
ws = wb['Товары']

rows = list(ws.iter_rows(min_row=1, values_only=True))
header = rows[0]
assert header == (
    'Бренд', 'Категория', 'Артикул продавца', 'Артикулы WB', 'Наименование',
    'Альтернативные наименования', 'ТНВЭД', 'Повторов в выгрузках',
), header

keywords = ('xbox', 'microsoft', 'майкрософт', 'иксбокс')
matches = []
for i, row in enumerate(rows[1:], start=2):
    hay = ' '.join(str(v) for v in row if v is not None).lower()
    if any(k in hay for k in keywords):
        matches.append({'row_number': i, **dict(zip(header, row))})

by_brand = {}
for m in matches:
    by_brand.setdefault(m['Бренд'], []).append(m)

selected_row = next(m for m in matches if m['Артикул продавца'] == 'XXU-00015')

result = {
    'catalog_file': 'data/catalog_2026-09-21_filtered.xlsx',
    'sheet': 'Товары',
    'schema_columns': list(header),
    'schema_note': (
        'Exactly 8 columns; no dedicated manufacturer/region-code field. '
        '"Артикул продавца" is seller-entered free text, not verified against any '
        'manufacturer registry by the catalog itself.'
    ),
    'search_keywords_case_insensitive': list(keywords),
    'total_rows_scanned': len(rows) - 1,
    'total_matches': len(matches),
    'brand_label_breakdown': {
        brand: {
            'row_count': len(items),
            'row_numbers': [it['row_number'] for it in items],
            'categories': sorted({it['Категория'] for it in items}),
        }
        for brand, items in by_brand.items()
    },
    'brand_separation_decision': {
        'rule_applied': (
            'Brands are taken from the catalog "Бренд" column, never inferred from the '
            'word "Xbox" appearing inside "Наименование". Two distinct brand labels were '
            'found among Xbox-mentioning rows and are kept separate.'
        ),
        'Microsoft': (
            '45 rows, brand label "Microsoft" — first-party Xbox consoles, gamepads, '
            'headsets, accessories, and one unrelated Microsoft mouse. This is the brand '
            'family in scope for this stage.'
        ),
        'Asus': (
            '3 rows, brand label "Asus", category "Игровые консоли" — "ROG Xbox Ally" / '
            '"ROG Xbox Ally X" handhelds. These are Asus-branded Windows handhelds '
            'co-marketed with the Xbox name; the catalog itself attributes them to Asus, '
            'not Microsoft. NOT merged into the Microsoft/Xbox brand family and NOT in '
            'scope for this stage (Asus was not investigated).'
        ),
    },
    'all_matched_rows': matches,
    'selected_row': selected_row,
    'selection_reason': (
        'Row 9661 (seller article XXU-00015, brand Microsoft, category '
        '"Игровые консоли") names "Игровая консоль Xbox Series S Carbon 1TB". '
        'Selected over the other 44 Microsoft rows because its "Наименование" carries '
        'three independent, checkable model/variant descriptors in one string: '
        '(1) product line — Xbox Series S (current console generation, distinct from '
        'the older Xbox One family also present in this brand), '
        '(2) storage capacity — 1TB, which is itself a variant marker because Xbox '
        'Series S also ships as a 512GB base edition (see row 9658, RRS-00011, same '
        'brand/category, "Xbox Series S 512 ГБ"), '
        '(3) color/finish — Carbon (i.e. the Carbon Black finish paired with the 1TB '
        'capacity, as opposed to the base white 512GB unit). '
        'A current, still-supported product line was preferred over the discontinued '
        'Xbox One family (rows 9649-9657) to maximize the chance that an official '
        'product/support page for the exact variant is still live. Gamepad color rows '
        '(e.g. 9622-9648) were also detailed but a console was preferred as the more '
        'central hardware identity for a first Xbox/Microsoft cycle.'
    ),
    'rows_not_selected_but_noted': {
        'RRS-00011_row_9658': 'Xbox Series S 512 GB — same line, base capacity, used as the contrasting variant that makes the 1TB Carbon capacity/color distinction meaningful.',
        'RRT-00015_row_9660': 'Xbox Series X — plain name, no explicit capacity/color descriptor in "Наименование", less detailed than the selected row.',
    },
}

OUT.mkdir(parents=True, exist_ok=True)
(OUT / 'offline_row_analysis.json').write_text(
    json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8'
)
print('matches:', len(matches))
print('selected:', selected_row)
