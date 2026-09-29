"""Stage 9.1 -- fully offline. Review every official PlayStation route already
discovered in Stage 8.2 / Stage 9 to determine whether a "substantial
difference" between the two catalog rows exists that would justify a bounded
network check, and whether any KNOWN (not invented) route could resolve it.
No network access in this script."""
import json
from pathlib import Path

ROOT = Path(r'A:\work\dev\product_cards_mvp')
OUT = ROOT / 'reports/source_census_2026-09-22_stage9_1'

controllers_link_index = json.loads(
    (ROOT / 'reports/source_census_2026-09-22_stage8_2/link_index/ps_controllers_cat.json').read_text(encoding='utf-8')
)
dualsense_cosmic_links = [
    l for l in controllers_link_index
    if 'dualsense' in json.dumps(l, ensure_ascii=False).lower() and 'cosmic' in json.dumps(l, ensure_ascii=False).lower()
]

stage9_evidence = json.loads((ROOT / 'reports/source_census_2026-09-22_stage9/evidence.json').read_text(encoding='utf-8'))
stage9_product_fetch = json.loads((ROOT / 'reports/source_census_2026-09-22_stage9/raw/product_fetch.json').read_text(encoding='utf-8'))

review = {
    'schema_version': 'stage9_1_known_routes_review.v1',
    'method': 'Re-reads already-persisted Stage 8.2 and Stage 9 evidence files on disk -- 0 new network requests.',
    'route_1_controllers_category_link_index': {
        'source': 'reports/source_census_2026-09-22_stage8_2/link_index/ps_controllers_cat.json (90 links, from direct.playstation.com/en-us/accessories/controllers-and-remotes)',
        'finding': f'Exactly {len(dualsense_cosmic_links)} link(s) on the entire controllers category page match both "DualSense" and "Cosmic Red".',
        'links_found': dualsense_cosmic_links,
        'interpretation': (
            'PS Direct (the checked, first-party US storefront) lists exactly ONE product page for '
            '"DualSense ... Cosmic Red" -- there is no second, differently-coded official page for a '
            'distinguishable regional/factory variant to compare against. This is a known route (already '
            'crawled in Stage 8.2), not an invented one, and it rules out the possibility that a second, '
            'separately-identifiable official listing exists on this storefront.'
        ),
    },
    'route_2_product_page_support_links': {
        'source': 'reports/source_census_2026-09-22_stage9/evidence.json, field instruction_manual',
        'finding': stage9_evidence['fields']['instruction_manual']['evidence'],
        'interpretation': (
            'Already checked in Stage 9: the only /support/ links present on the verified product page are '
            'generic e-commerce policy pages (financing, FAQs, shipping, cancellations, subscriptions) -- none '
            'is specific to this SKU or capable of confirming a manufacturer/regional code.'
        ),
    },
    'route_3_product_page_itself': {
        'source': 'reports/source_census_2026-09-22_stage9/raw/product_fetch.json',
        'finding': {
            'code_context_hits': stage9_product_fetch['code_context_hits'],
            'identity_term_matches_CFI': {
                'CFI-ZCT1J': stage9_product_fetch['identity_term_matches']['CFI-ZCT1J'],
                'CFI-ZCT1W': stage9_product_fetch['identity_term_matches']['CFI-ZCT1W'],
            },
        },
        'interpretation': (
            'Already fetched and searched in Stage 9: zero occurrences of any CFI- pattern anywhere on the '
            'page. Per this stage\'s explicit instruction, this absence is NOT treated as disproof that the '
            "page corresponds to either seller SKU -- it only means the page does not DISPLAY that code, which "
            'is unsurprising for a US direct-to-consumer storefront that uses its own internal numeric sku '
            'system (1000050734) rather than exposing Sony\'s manufacturer part number to retail buyers.'
        ),
    },
    'substantial_difference_offline_finding': {
        'found': False,
        'basis': 'See offline_row_analysis.json -- the only differing field that could plausibly indicate a real variant distinction is the seller-assigned article string, which per instruction cannot be used alone as proof.',
    },
    'known_route_capable_of_confirming_a_difference': {
        'exists': False,
        'basis': (
            'All three known, already-discovered official routes (controllers category listing, the product '
            "page's own support links, the product page's own body/microdata) have been checked -- across "
            'Stage 8.2 and Stage 9 -- and none exposes a manufacturer/regional code or a second distinguishable '
            'listing. No further known route remains to check.'
        ),
    },
    'decision': (
        'Per instruction ("только если офлайн данные показывают существенное различие между строками, '
        'проведи ограниченную проверку"), no substantial difference was found offline, so no new bounded '
        'network check is performed this stage. 0 new HTTP requests were made. www.playstation.com and '
        'support.playstation.com remain pre-declared-but-uncontacted, unchanged from Stage 9, since no known '
        'route leads there for this specific question either.'
    ),
}

(OUT / 'known_routes_review.json').write_text(json.dumps(review, indent=2, ensure_ascii=False), encoding='utf-8')
print('wrote known_routes_review.json')
