"""Stage 10.1 -- offline provenance record for the two Xbox hosts, no new network requests.

Source: Stage 10's own bounded_probe_result.json (request #3), read-only.
"""
import json
from pathlib import Path

ROOT = Path(r'A:\work\dev\product_cards_mvp')
STAGE10 = ROOT / 'reports/source_census_2026-09-23_stage10'
OUT = ROOT / 'reports/source_census_2026-09-23_stage10_1'

stage10_probe = json.loads((STAGE10 / 'bounded_probe_result.json').read_text(encoding='utf-8'))
origin_request = next(r for r in stage10_probe['request_log'] if r['seq'] == 3)

assert origin_request['requested_url'] == 'https://support.microsoft.com/en-us/all-products'
assert origin_request['final_url'] == 'https://support.microsoft.com/en-us/all-products-list'
assert origin_request['http_status'] == 200

all_off_host = stage10_probe['off_host_links_seen_but_not_followed']
in_scope_hosts = ('www.xbox.com', 'support.xbox.com')

from urllib.parse import urlsplit

in_scope_links = [u for u in all_off_host if (urlsplit(u).hostname or '') in in_scope_hosts]
out_of_scope_this_stage = [u for u in all_off_host if (urlsplit(u).hostname or '') not in in_scope_hosts]

by_host = {}
for url in in_scope_links:
    host = urlsplit(url).hostname
    by_host.setdefault(host, []).append(url)

result = {
    'origin_page': {
        'requested_url': origin_request['requested_url'],
        'final_url_after_redirect': origin_request['final_url'],
        'redirect_chain': origin_request['redirect_chain'],
        'http_status': origin_request['http_status'],
        'fetched_at_stage': 'Stage 10',
        'fetch_evidence': 'reports/source_census_2026-09-23_stage10/bounded_probe_result.json#request_log[2]',
        'note': (
            'support.microsoft.com is itself official_status=official_verified '
            '(source_research.v1.json). This page was fetched directly (HTTP 200, no '
            'protection observed) and its own global navigation names "Xbox" as a Microsoft '
            'product line.'
        ),
    },
    'links_in_scope_for_this_stage': by_host,
    'links_excluded_this_stage_explicit_user_scope': out_of_scope_this_stage,
    'exclusion_reason': (
        'The task explicitly names only www.xbox.com and support.xbox.com as candidates for '
        'this stage. www.microsoft.com/en-us/store/b/xbox* links seen in Stage 10 are a '
        'different host, not named, and are left untouched (still recorded as unconfirmed '
        'leads in Stage 10\'s own card.json).'
    ),
    'per_host_reasoning': {
        'www.xbox.com': {
            'why_plausibly_official': (
                'Linked directly from support.microsoft.com\'s own confirmed-official global '
                'navigation, under a menu item labeled "XBOX" / "Shop XBOX", i.e. Microsoft\'s '
                'own site identifies this host as its product destination for Xbox. This is '
                'ownership-adjacent evidence (a first-party page pointing to the candidate), '
                'the same evidence *type* already used for the existing official_domains.v1.json '
                'entries (e.g. LG\'s "official_country_selector_or_corporate_page"), but it is '
                'not yet content-verified for this specific host -- that verification is what '
                'this stage\'s bounded probe performs before any promotion decision.'
            ),
            'candidate_role_before_verification': 'product/store (commercial) -- the two already-seen sample URLs on this host are game-store listings, not console hardware, so hardware product-page presence is not yet established and must be found via same-host navigation/sitemap, not guessed.',
        },
        'support.xbox.com': {
            'why_plausibly_official': (
                'Same provenance as above -- linked from support.microsoft.com\'s own '
                'navigation as "Xbox". The "support." subdomain naming convention parallels '
                'the already-verified support.microsoft.com itself.'
            ),
            'candidate_role_before_verification': 'support -- the one already-seen sample URL on this host is a PC-gaming help article, consistent with a support role, not a commercial product-page role.',
        },
    },
}

OUT.mkdir(parents=True, exist_ok=True)
(OUT / 'offline_provenance.json').write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
print(json.dumps(by_host, indent=2))
print('excluded:', out_of_scope_this_stage)
