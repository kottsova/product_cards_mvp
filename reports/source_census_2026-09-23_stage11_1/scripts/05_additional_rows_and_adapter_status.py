"""Stage 11.1 -- select up to 2 additional HYPERX catalog rows (offline
catalog read, no new request), compare them against the 2 freshly-fetched
candidate pages, and build the adapter-repeatability status: which
extraction components actually yielded real values on which pages."""
import json
from pathlib import Path

import openpyxl

ROOT = Path(r'A:\work\dev\product_cards_mvp')
OUT = ROOT / 'reports/source_census_2026-09-23_stage11_1'
CATALOG = ROOT / 'data/catalog_2026-09-21_filtered.xlsx'

wb = openpyxl.load_workbook(CATALOG, data_only=True, read_only=True)
ws = wb['Товары']
rows = list(ws.iter_rows(min_row=1, values_only=True))
header = rows[0]


def find_row(seller_article):
    for i, row in enumerate(rows[1:], start=2):
        rd = dict(zip(header, row))
        if rd.get('Артикул продавца') == seller_article and rd.get('Бренд') == 'HYPERX':
            return {'row_number': i, **rd}
    return None


keyboard_row = find_row('7G7A4AA#ACB')
mouse_row = find_row('A1KY6AA')

phase3 = json.loads((OUT / 'phase3_candidate_product_pages_fetch.json').read_text(encoding='utf-8'))
kb = phase3['results']['keyboard']
ms = phase3['results']['mouse']
kb_product = kb['json_ld_products_raw'][0]
ms_product = ms['json_ld_products_raw'][0]

additional_rows = {
    'keyboard': {
        'catalog_row': keyboard_row,
        'discovery_method': 'Found via https://hyperx.com/collections/gaming-keyboards, an already-known nav link from the microphone product page fixture -- not guessed.',
        'candidate_url': kb['url'],
        'identity_check': {
            'catalog_seller_article': keyboard_row['Артикул продавца'],
            'official_page_sku': kb_product.get('sku'),
            'exact_match': keyboard_row['Артикул продавца'] == kb_product.get('sku'),
            'base_code_match': keyboard_row['Артикул продавца'].split('#')[0] == kb_product.get('sku', '').split('#')[0],
            'mismatch_detail': (
                f"Catalog row names this the (RU) market variant (suffix #ACB). The fetched "
                f"official page's own additionalProperty explicitly states "
                f"'Keyboard Layout: US Layout' and its offer name reads "
                f"'{kb_product.get('offers', {}).get('name')}' -- suffix #ABA. Same base model "
                f"code (7G7A4AA), different regional/layout suffix. This is a real, evidenced "
                f"identity GAP, not a confirmed match -- no RU-specific hyperx.com page was "
                f"found, and none was guessed to paper over the gap."
            ),
            'conclusion': 'model_line_confirmed_exact_regional_variant_not_confirmed',
        },
    },
    'mouse': {
        'catalog_row': mouse_row,
        'discovery_method': 'Found via https://hyperx.com/collections/gaming-mice, an already-known nav link from the microphone product page fixture -- not guessed.',
        'candidate_url': ms['url'],
        'identity_check': {
            'catalog_seller_article': mouse_row['Артикул продавца'],
            'official_page_sku': ms_product.get('sku'),
            'exact_match': mouse_row['Артикул продавца'] == ms_product.get('sku'),
            'conclusion': 'confirmed_by_exact_code_match',
        },
    },
}

# --- Per-component, per-page evidence table (the actual point of this stage) ---
def additional_property_summary(product):
    props = product.get('additionalProperty', [])
    populated = [p for p in props if p.get('value')]
    return {'total_properties': len(props), 'populated_with_real_values': len(populated),
            'populated_names': [p['name'] for p in populated]}


component_matrix = {
    'pages_examined_this_project_total': 5,
    'pages_examined_this_project_list': [
        'microphone (QuadCast 2S, Stage 11) -- LIVE fetch, values available',
        'keyboard (Alloy Rise 75, this stage) -- LIVE fetch, values available',
        'mouse (Pulsefire Fuse, this stage) -- LIVE fetch, values available',
        'gaming headset (Cloud Alpha Air, Stage 8.1) -- sanitized fixture only, no catalog match, values not retained by design',
        'keyboard+mouse bundle (Alloy Rise 75 + Pulsefire Haste 2 S, Stage 8) -- sanitized fixture only, values not retained by design',
    ],
    'identity_json_ld_sku_field': {
        'shape_present_and_stable': 'confirmed on all 3 live-fetched pages (microphone, keyboard, mouse) -- same signature match to Stage 8.1\'s original contract',
        'value_matches_catalog_row_exactly': {
            'microphone_9A273AA': True,
            'mouse_A1KY6AA': True,
            'keyboard_7G7A4AA': 'base code only -- exact suffix mismatch (US vs RU layout variant)',
        },
        'conclusion': (
            'The FIELD is a compatible_primitive (present, stable shape, 3/3 pages). Whether its '
            'VALUE matches a given catalog row exactly is NOT guaranteed by the field existing -- '
            'it must be checked per catalog row, per market. 2 of 3 checked rows matched exactly; '
            'one did not, for a real, identified reason (regional layout variant).'
        ),
    },
    'specifications_additionalProperty_json_ld': {
        'shape_present_on_all_3_pages': True,
        'value_population_by_page': {
            'microphone': additional_property_summary(json.loads((OUT / '..' / 'source_census_2026-09-23_stage11' / 'phase1_robots_and_product_fetch.json').read_text(encoding='utf-8'))['json_ld_products_raw'][0]),
            'keyboard': additional_property_summary(kb_product),
            'mouse': additional_property_summary(ms_product),
        },
        'conclusion': (
            'The additionalProperty FIELD is present on all 3 pages (compatible_primitive shape). '
            'Its VALUE population is NOT reliable across pages -- fully empty on the microphone, '
            'partially populated on the mouse, mostly populated on the keyboard. This must be '
            'checked live per page; a shared reader cannot assume non-empty values just because '
            'the field exists.'
        ),
    },
    'specifications_dom_table_fallback': {
        'shape_present_on_all_3_pages': True,
        'note': 'specs-label/specs-value <td> pairs inside a <table>, not literally Stage 8.1\'s abstracted "dl:dt+dd"/"accordion" labels, but functionally the same role.',
        'value_population_by_page': {'microphone': 'confirmed real values (Stage 11)', 'keyboard': '20 label/value pairs found', 'mouse': '21 label/value pairs found'},
        'conclusion': 'This DOM table is the reliably-populated specification source on all 3 pages sampled -- confirmed compatible_primitive at both shape AND value level, unlike the JSON-LD additionalProperty reader above.',
    },
    'media_json_ld_image_field': {
        'shape_and_value_present_on_all_3_pages': True,
        'largest_advertised_size_by_page': {
            'microphone': '4000x4000 (via offers.image + og:image)',
            'keyboard': '4000x4000 (via Product.image)',
            'mouse': '1500x1500 (via Product.image) -- genuinely smaller; not upscaled or guessed',
        },
        'conclusion': 'compatible_primitive -- reliable on all 3 pages, real dimensions each time, no invented CDN transforms.',
    },
    'media_dom_responsive_srcset': {
        'shape_present_on_all_3_pages': True,
        'CORRECTION_to_stage8_1_characterization': (
            'On all 3 live-fetched pages, every srcset attribute containing a real comma-'
            'separated multi-width list belongs to the shared site theme logo image '
            '(hyperxlogo_150x.svg / _300x.svg), never to a product photo. Every product-photo '
            'srcset/src attribute is a SINGLE URL, not a responsive width list. Stage 8.1\'s '
            '"responsive_srcset" DOM marker fires because the attribute exists somewhere on the '
            'page, but it does not describe genuine per-product responsive images. The actually '
            'reliable size signal is the JSON-LD image.width/height, not this DOM marker.'
        ),
    },
    'documents': {
        'pdf_links_found_across_all_5_project_pages': 0,
        'conclusion': 'insufficient_evidence to claim documents are ever exposed via a PDF link on hyperx.com product pages -- a stable, now 5-page-wide, negative finding. Not claimed as proof no HyperX product page anywhere has one.',
    },
}

output = {'additional_catalog_rows': additional_rows, 'component_matrix': component_matrix}
(OUT / 'additional_rows_and_adapter_status.json').write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding='utf-8')
print(json.dumps(additional_rows['keyboard']['identity_check'], indent=2, ensure_ascii=False))
print(json.dumps(additional_rows['mouse']['identity_check'], indent=2, ensure_ascii=False))
