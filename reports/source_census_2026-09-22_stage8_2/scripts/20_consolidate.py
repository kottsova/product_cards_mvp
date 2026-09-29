import json
from pathlib import Path

OUT = Path(r'A:\work\dev\product_cards_mvp\reports\source_census_2026-09-22_stage8_2')


def load(name):
    p = OUT / name
    return json.loads(p.read_text(encoding='utf-8')) if p.exists() else None


catalog_raw = load('catalog_samples_raw.json')
samsung_step1 = load('samsung_step1.json')
samsung_step2 = load('samsung_step2.json')
samsung_step3 = load('samsung_step3.json')
samsung_products = load('samsung_products.json')
lg_step1 = load('lg_step1.json')
lg_products = load('lg_products.json')
ps_step1 = load('playstation_step1.json')
ps_products = load('playstation_products.json')
ps_id_check = load('ps_controller_identity_check.json')
run_state = load('run_state.json')

# ---------------------------------------------------------------------------
# catalog_samples.json -- the catalog rows selected per brand, and whether an
# actual bounded search/sitemap route was executed for them in this stage.
# ---------------------------------------------------------------------------
SEARCHED_FAMILIES = {'samsung', 'lg', 'playstation'}
FAMILY_MAP = {
    'Samsung': 'samsung', 'Apple': 'apple', 'LG': 'lg', 'JBL': 'jbl',
    'Playstation': 'playstation', 'Razer': 'razer', 'HIPER': 'hiper', 'Microsoft': 'microsoft',
}
catalog_samples = []
seen_pairs = set()
for row in catalog_raw:
    brand = row['catalog_brand_label']
    fam = FAMILY_MAP[brand]
    key = (brand, row['catalog_category'])
    # Keep only the first article per (brand, category) pair as the representative pick,
    # to respect "at most two products per brand, one per massive category".
    if key in seen_pairs:
        continue
    seen_pairs.add(key)
    catalog_samples.append({
        'catalog_brand_label': brand,
        'source_family': fam,
        'catalog_category': row['catalog_category'],
        'seller_article': row['seller_article'],
        'wb_article': row['wb_article'],
        'name': row['name'],
        'search_query_used': f"{brand} {row['seller_article']} {row['name']}".strip(),
        'in_scope_for_stage8_2_network_pass': fam in SEARCHED_FAMILIES,
        'out_of_scope_reason': None if fam in SEARCHED_FAMILIES else (
            'jbl: both jbl.com and support.jbl.com are http_blocked from Stage 8; not retried per host-stop policy.' if fam == 'jbl' else
            'No Stage 8.2 queue entry for this profile in the internal_http_search or sitemap_or_catalog_feed groups (it sits in official_category / support_first / regional_official_domain, which this stage does not execute).'
        ),
    })

# ---------------------------------------------------------------------------
# product_page_fixtures.json
# ---------------------------------------------------------------------------
fixtures_out = []


def add_fixture(source_family, profile_id, catalog_ref, url, discovery_route, page_result, catalog_identity_result,
                 identity_reasoning, struct_summary, limitations, next_safe_route):
    fixtures_out.append({
        'source_family': source_family,
        'profile_id': profile_id,
        'catalog_sample_ref': catalog_ref,
        'url': url,
        'discovery_route': discovery_route,
        'product_page_fixture_result': page_result,
        'catalog_identity_result': catalog_identity_result,
        'identity_reasoning': identity_reasoning,
        'structure_summary': struct_summary,
        'limitations': limitations,
        'next_safe_route': next_safe_route,
    })


# --- Samsung ---
st = samsung_products['samsung_tv']
sb = samsung_products['samsung_buds']
add_fixture('samsung', 'samsung_kz_02d9e6',
            {'catalog_category': 'Телевизоры', 'seller_article': 'QE100QN80FUX (targeted, not reached)'},
            st['url'], 'sitemap_or_catalog_feed: robots-declared sitemap index -> b2c-sitemap.xml -> vd-sitemap.xml -> product URL',
            'verified', 'insufficient',
            'Reached TV is UE43N5300AUXCE, a different model from the targeted catalog article QE100QN80FUX (a 100" premium set not present in the ~52-URL TV sitemap slice actually served). Brand (Samsung) and category (TV) confirmed; exact catalog article not reached, so no variant/model comparison was possible.',
            {'is_product_page': st['is_product_page'], 'identity': st['identity'], 'specs': st['specs'],
             'media_json_paths': st['media_json_paths'], 'media_dom': st['media_dom'], 'docs': st['docs'], 'cms': st['cms']},
            ['sku present, no mpn/gtin -> unverified_sku_meaning, same as most non-Bosch families', 'specifications layer empty in static HTML (likely client-rendered spec tab)'],
            'Try samsung_kr (sec) consumer_sitemap.xml, or samsung_kz_02d9e6 vd-sitemap.xml deeper pages (>300 loc), for the exact 100in QLED article.')
add_fixture('samsung', 'samsung_kz_02d9e6',
            {'catalog_category': 'Смартфоны', 'seller_article': 'SM-G780GZRDSKZ (targeted, not reached)'},
            sb['url'], 'sitemap_or_catalog_feed: robots-declared sitemap index -> b2c-sitemap.xml -> im-sitemap.xml -> product URL',
            'verified', 'insufficient',
            'im-sitemap.xml (the "IT & Mobile" sub-sitemap) contained only audio-sound and mobile-accessories paths in its 300 <loc> entries -- no /smartphones/ path segment appeared at all within the bounded traversal, so no Galaxy phone URL was reached. Reached a Galaxy Buds3 FE product instead (same im-sitemap, audio-sound path), which is Samsung-brand and mobile-category-adjacent but not the targeted smartphone.',
            {'is_product_page': sb['is_product_page'], 'identity': sb['identity'], 'specs': sb['specs'],
             'media_json_paths': sb['media_json_paths'], 'media_dom': sb['media_dom'], 'docs': sb['docs'], 'cms': sb['cms']},
            ['Smartphones (Galaxy S-series) not located inside b2c/im/vd/assorted sitemaps within the bounded 300-loc-per-file sample; a dedicated mobile-phone sitemap file may exist under a different name not discoverable without inventing a URL.'],
            'Probe robots.txt on samsung.com/kz_ru specifically for a mobile/phones-named sitemap declaration not yet seen, or use samsung_us b2c-sitemap equivalent to cross-check naming.')

# --- LG ---
lt = lg_products['lg_tv']
lw = lg_products['lg_washer']
add_fixture('lg', 'lg_kz',
            {'catalog_category': 'Телевизоры', 'seller_article': '27ART10AKPL / 27LX5QKNA / 32LB650B6LA (targeted, not reached)'},
            lt['url'], 'sitemap_or_catalog_feed: robots-declared sitemap index -> kz-gpone-index.xml -> kz-pdp-sitemap-hreflang.xml -> product URL',
            'candidate', 'insufficient',
            'URL came from a sitemap explicitly named "pdp" (Product Detail Page) by LG itself, and the model slug (43UM7100PLB) is a real LG TV model -- but the fetched static HTML carried zero JSON-LD Product objects and zero microdata Product nodes, so the automated structural test cannot confirm it is a single-product page vs. a client-side-rendered shell. Matches Stage 8s prior javascript_only finding for other LG profiles.',
            {'is_product_page': lt['is_product_page'], 'identity': lt['identity'], 'specs': lt['specs'],
             'media_json_paths': lt['media_json_paths'], 'media_dom': lt['media_dom'], 'docs': lt['docs'], 'cms': lt['cms']},
            ['product_objects=0 despite a PDP-labeled sitemap and a real-looking model slug -- LG.com/kz likely renders identity/spec data client-side (Next.js) and does not embed it in the initial HTML response.'],
            'Manual review / embedded-state extraction research (out of this stages scope); do not mark official_exact_product_not_found from this single route.')
add_fixture('lg', 'lg_kz',
            {'catalog_category': 'Стиральные машины', 'seller_article': 'F2J3HS0W / F2J3HS4L / F2J3HS8W (targeted, not reached)'},
            lw['url'], 'sitemap_or_catalog_feed: robots-declared sitemap index -> kz-gpone-index.xml -> kz-pdp-sitemap-hreflang.xml -> product URL',
            'candidate', 'insufficient',
            'Same pattern as the TV page: real PDP-sitemap URL (model F2V5HS2S, a plausible near-generation sibling of the targeted F2J3 series, not an exact match), zero JSON-LD/microdata Product objects in the static response.',
            {'is_product_page': lw['is_product_page'], 'identity': lw['identity'], 'specs': lw['specs'],
             'media_json_paths': lw['media_json_paths'], 'media_dom': lw['media_dom'], 'docs': lw['docs'], 'cms': lw['cms']},
            ['Same client-side-rendering gap as the TV page.'],
            'Same as above -- manual review / embedded-state extraction research, not a network retry.')

# --- PlayStation ---
pc = ps_products['ps_controller']
pg = ps_products['ps_game']
add_fixture('playstation', 'playstation_global_candidate',
            {'catalog_category': 'Геймпады', 'seller_article': 'CFI-ZCT1J 02'},
            pc['url'], 'sitemap_or_catalog_feed: already-known PS Direct collection page (direct.playstation.com/en-us/collections/wolverine, reused from Stage 8 cache, 0 new requests) -> first-party navigation to accessories/controllers-and-remotes category -> product URL',
            'verified', 'exact_model',
            'Page text contains "DualSense", "Cosmic Red" and "PS5" -- brand, product line and color variant name all match the catalog row (\'Геймпад DualSense для PS5 Cosmic Red\') textually. The manufacturer regional part number CFI-ZCT1J was NOT found in the page text, and the structural contract only exposes microdata sku/name (no extracted value comparison is performed by the sanitized census pipeline, by design). Classified exact_model rather than exact_variant: model and stated color variant are corroborated, but the manufacturer code itself is unconfirmed on this regional storefront, so full SKU-level certainty is not claimed.',
            {'is_product_page': pc['is_product_page'], 'identity': pc['identity'], 'specs': pc['specs'],
             'docs': pc['docs'], 'cms': pc['cms']},
            ['Identity is exposed via schema.org Microdata (itemprop="sku"/"name"), not JSON-LD -- the first confirmed non-JSON-LD identity source in this whole review.', 'model_semantics classifier reports marketing_name_only here even though a sku microdata property is present, because the existing inspect_structure() logic only feeds JSON-LD `fields` into that specific classification, not microdata `props` -- a real gap in Stage 8s own contract inspector, noted as an architecture observation, not fixed in this stage.'],
            'If exact SKU confirmation is required, a manual document/value-level review of this already-verified page is the next step, not a further network search.')
add_fixture('playstation', 'playstation_global_candidate',
            {'catalog_category': 'Диски с играми', 'seller_article': "007 First Light PS5 (targeted, not reached)"},
            pg['url'], 'sitemap_or_catalog_feed: same PS Direct collection page -> first-party navigation to games/catalog -> /buy-games/ product URL',
            'verified', 'family_only',
            'A real /buy-games/ product page was reached (Ghost of Yotei Collectors Edition PS5), confirming PS Directs buy-games/ URL convention and structural contract -- but it is a different title from the catalog-targeted "007 First Light PS5", which was not found as a direct.playstation.com/buy-games/ link within the bounded navigation performed (007 First Light appeared only as a DualSense controller limited-edition bundle, not as its own /buy-games/ listing, in the pages reached).',
            {'is_product_page': pg['is_product_page'], 'identity': pg['identity'], 'specs': pg['specs'],
             'docs': pg['docs'], 'cms': pg['cms']},
            ['Same microdata-only identity pattern as the controller page.', 'PS Direct sells hardware/accessories/collectors editions, not plain physical game discs as a general rule -- the catalogs "Диски с играми" category may not map cleanly onto PS Direct at all; a games-focused route (e.g. the PlayStation Store, a different official domain) may be more appropriate for that specific catalog category, and is out of this stages scope to open.'],
            'For the game-disc category specifically, consider PlayStation Store (official digital storefront) as a separate, still-official route in a later stage, rather than retrying PS Direct.')

json.dump(catalog_samples, open(OUT / 'catalog_samples.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
json.dump(fixtures_out, open(OUT / 'product_page_fixtures.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
print('catalog_samples:', len(catalog_samples))
print('product_page_fixtures:', len(fixtures_out))
