import json
from pathlib import Path

OUT = Path(r'A:\work\dev\product_cards_mvp\reports\source_census_2026-09-22_stage8_2_1')


def load(name):
    p = OUT / name
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else None


run_state = load('run_state.json')
da_memory = load('da_memory_check.json')
smart_cat = load('smartphones_cat_check.json')
smart_products = load('smartphone_products.json')

# ---------------------------------------------------------------------------
# catalog_samples.json
# ---------------------------------------------------------------------------
catalog_samples = [
    {
        'catalog_brand_label': 'Samsung',
        'source_family': 'samsung',
        'catalog_category': 'Смартфоны',
        'seller_article': '488776SM-G780GZRDSKZ',
        'wb_article': '112421624',
        'full_name': 'Galaxy S20 FE 128GB',
        'base_model': 'Galaxy S20 FE',
        'model_code_prefix': 'SM-G780G',
        'memory_variant': '128GB',
        'color_variant': 'encoded in SKU suffix "ZRD" (not spelled out in catalog text; Samsung KZ SKU convention places a 2-letter color code before the regional "D"+"SKZ" suffix -- treated as evidence of a distinct color variant, not read as a verified color name)',
        'note_do_not_conflate': 'base_model "Galaxy S20 FE" is recorded separately from the 128GB memory variant and the ZRD color-code variant, per instructions not to merge base model with a specific memory/color configuration.',
        'search_query_used': 'Samsung 488776SM-G780GZRDSKZ Galaxy S20 FE 128GB',
    },
    {
        'catalog_brand_label': 'Samsung',
        'source_family': 'samsung',
        'catalog_category': 'Смартфоны',
        'seller_article': '491953SM-F926BZGGSKZ',
        'wb_article': '112475603',
        'full_name': 'Galaxy Z Fold3 5G 512GB',
        'base_model': 'Galaxy Z Fold3 5G',
        'model_code_prefix': 'SM-F926B',
        'memory_variant': '512GB',
        'color_variant': 'encoded in SKU suffix "ZGG" (not spelled out in catalog text; same convention as above, not read as a verified color name)',
        'note_do_not_conflate': 'base_model "Galaxy Z Fold3 5G" is recorded separately from the 512GB memory variant and the ZGG color-code variant.',
        'search_query_used': 'Samsung 491953SM-F926BZGGSKZ Galaxy Z Fold3 5G 512GB',
    },
]
json.dump(catalog_samples, open(OUT / 'catalog_samples.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)

# ---------------------------------------------------------------------------
# sitemap_evidence.json
# ---------------------------------------------------------------------------
sitemap_evidence = {
    'schema_version': 'stage8_2_1_sitemap_evidence.v1',
    'host': 'www.samsung.com',
    'scope_path': 'kz_ru',
    'offline_evidence_reused': {
        'robots_txt': {
            'source': 'reports/source_census_2026-09-22_stage7/source_snapshots.sqlite3 (samsung_kz, https://www.samsung.com/robots.txt)',
            'new_requests_needed': 0,
            'finding': 'robots.txt declares one Sitemap: line per region (Sitemap:https://www.samsung.com/kz_ru/sitemap.xml among ~90 others). No mobile/phone-specific sitemap is declared in robots.txt itself.',
        },
        'sitemap_xml_index': {
            'source': 'Stage 8.2 offline reprocessing (reports/source_census_2026-09-22_stage8_2/raw/offline_reprocess.json)',
            'new_requests_needed': 0,
            'finding': 'kz_ru/sitemap.xml is a sitemap index with 5 branches: b2c-sitemap.xml, top_sitemap.xml, business/top-sitemap.xml, business/b2b-sitemap.xml, support/sitemap.xml. Only b2c-sitemap.xml has consumer-catalog naming; the others are marketing/B2B/support by name and were not opened (no smartphone-related naming evidence).',
        },
        'b2c_sitemap_already_checked_in_stage8_2': {
            'branches': ['vd-sitemap.xml (visual display: TVs/audio/monitors/projectors -- 300 links, 0 smartphones)',
                         'im-sitemap.xml (IT & mobile -- 300 links, but only mobile-accessories(281) and audio-sound(19); 0 smartphones)',
                         'assorted-sitemap.xml (marketing/promo pages -- 300 links, 0 smartphones)'],
            'new_requests_needed': 0,
        },
    },
    'new_requests_this_stage': [
        {
            'url': 'https://www.samsung.com/kz_ru/da-sitemap.xml',
            'reason': 'Last unchecked branch of the already-known b2c-sitemap.xml index (digital appliances).',
            'result': 'content = home appliances (air-conditioners, cooking-appliances, dishwashers, home-appliances, microwave-ovens, refrigerators, air-care, home-appliance-accessories). 0 smartphone URLs.',
        },
        {
            'url': 'https://www.samsung.com/kz_ru/memory-sitemap.xml',
            'reason': 'Last unchecked branch of the already-known b2c-sitemap.xml index (memory/storage).',
            'result': 'content = memory-storage only (90 links, e.g. SSDs). 0 smartphone URLs.',
        },
        {
            'url': 'https://www.samsung.com/kz_ru/smartphones/all-smartphones/',
            'reason': 'NOT from the sitemap system -- a first-party navigation link discovered entirely offline on the already-known kz_ru homepage snapshot (0 new requests to find it). The homepage links to /kz_ru/smartphones/... paths that the b2c-sitemap.xml branches never referenced.',
            'result': 'A real, reachable /smartphones/ site section exists (family pages: galaxy-s/, galaxy-z/, galaxy-a/, plus /buy/ configurator links), but this category page itself returned only navigation-shaped links, not a flat product grid with SKU-bearing URLs (unlike tablets/watches links seen on the same page, e.g. .../galaxy-tab-s11-ultra-gray-256gb-sm-x936bzaaskz/buy/, which DO embed color+memory+model code).',
        },
        {
            'url': 'https://www.samsung.com/kz_ru/smartphones/galaxy-s25-ultra/',
            'reason': 'First-party link from the already-fetched smartphones/all-smartphones category page.',
            'result': 'is_product_page=false: zero JSON-LD Product objects, zero microdata Product nodes. Page text does confirm "Galaxy S25 Ultra" and "Samsung" are present.',
        },
        {
            'url': 'https://www.samsung.com/kz_ru/smartphones/galaxy-s26-ultra/buy/',
            'reason': 'First-party /buy/ configurator link from the same category page.',
            'result': 'Same as above: is_product_page=false, zero JSON-LD/microdata Product objects.',
        },
    ],
    'branches_deliberately_not_opened': [
        {'url': 'https://www.samsung.com/kz_ru/top_sitemap.xml', 'reason': 'No naming evidence connecting it to smartphones; opening it would mean loading an unproven branch, against instructions.'},
        {'url': 'https://www.samsung.com/kz_ru/business/top-sitemap.xml', 'reason': 'B2B/business branch by name, not consumer catalog.'},
        {'url': 'https://www.samsung.com/kz_ru/business/b2b-sitemap.xml', 'reason': 'B2B branch by name, not consumer catalog.'},
        {'url': 'https://www.samsung.com/kz_ru/support/sitemap.xml', 'reason': 'Support/documents branch by name, not a product catalog.'},
    ],
    'conclusion': {
        'sitemap_route_status': 'mobile_sitemap_no_product_urls',
        'detail': 'All 5 declared branches of the only proven consumer-catalog sitemap (b2c-sitemap.xml) were checked (3 in Stage 8.2, 2 in this stage) and none contain smartphone product URLs. A real /smartphones/ site section exists and was reached via first-party navigation (not the sitemap system), but its pages do not expose static structured product data, so no Product page fixture could be verified from it either.',
    },
}
json.dump(sitemap_evidence, open(OUT / 'sitemap_evidence.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)

# ---------------------------------------------------------------------------
# product_page_fixtures.json
# ---------------------------------------------------------------------------
fixtures_out = []
for name, catalog_ref in [
    ('samsung_phone_s25ultra', 'Not the targeted catalog SKU -- current-generation (2025) flagship, catalog rows are 2020-2022 models'),
    ('samsung_phone_s26ultra_buy', 'Not the targeted catalog SKU -- current-generation (2026) flagship, catalog rows are 2020-2022 models'),
]:
    d = smart_products[name]
    fixtures_out.append({
        'source_family': 'samsung',
        'profile_id': 'samsung_kz_02d9e6',
        'catalog_sample_ref': catalog_ref,
        'url': d['url'],
        'discovery_route': 'first-party navigation: kz_ru homepage (offline, 0 requests) -> smartphones/all-smartphones category page -> product/buy link',
        'product_page_fixture_result': 'candidate',
        'catalog_identity_result': 'insufficient',
        'identity_reasoning': (
            'Page text confirms the marketing model name and "Samsung" (identity_term_matches all true), but zero JSON-LD Product objects '
            'and zero microdata Product nodes were found in the static HTML -- the same client-side-rendering gap already seen on LG.com/kz '
            'in Stage 8.2. No code_fields (sku/mpn/gtin), no color, no memory variant are exposed statically, so this cannot be compared to '
            'the catalog rows (Galaxy S20 FE 128GB ZRD, Galaxy Z Fold3 5G 512GB ZGG) at all -- and even if it could, this is a different, '
            'current-generation model line, not the catalog-targeted one.'
        ),
        'structure_summary': {
            'is_product_page': d['is_product_page'], 'identity': d['identity'], 'specs': d['specs'],
            'media_json_paths': d['media_json_paths'], 'media_dom': d['media_dom'], 'docs': d['docs'], 'cms': d['cms'],
        },
        'limitations': [
            'product_objects=0: Samsung.com/kz_ru appears to use at least two different page templates -- the TV/audio-sound template (Stage 8.2, JSON-LD Product with .name/.sku) and the smartphone family/buy template (this stage, no static structured data at all).',
            'Galaxy family or marketing name matching text alone is explicitly not treated as exact_model, per instructions.',
        ],
        'next_safe_route': 'Manual review / embedded-state extraction research (out of this stage\'s scope, same architectural gap as LG); not a further network search on this route.',
    })
json.dump(fixtures_out, open(OUT / 'product_page_fixtures.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)

print('wrote catalog_samples.json, sitemap_evidence.json, product_page_fixtures.json')
