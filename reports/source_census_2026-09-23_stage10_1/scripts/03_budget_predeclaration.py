"""Stage 10.1 -- budget predeclaration, written BEFORE any HTTP request this stage."""
import json
from pathlib import Path

OUT = Path(r'A:\work\dev\product_cards_mvp\reports\source_census_2026-09-23_stage10_1')

budget = {
    'declared_at': '2026-09-23',
    'declared_before_any_request': True,
    'scope': (
        'Only the two hosts named by the user, provenance-linked from Stage 10\'s already-fetched '
        'support.microsoft.com page: www.xbox.com and support.xbox.com. Single catalog row in '
        'scope: XXU-00015 (Xbox Series S Carbon 1TB). No general Xbox census, no other catalog rows.'
    ),
    'allowed_hosts': ['www.xbox.com', 'support.xbox.com'],
    'allowed_hosts_reason': 'Explicitly named by the user; both already carry first-party-link provenance from Stage 10 (found on support.microsoft.com\'s own official navigation).',
    'seed_urls_already_known_not_guessed': [
        'https://www.xbox.com/',
        'https://support.xbox.com/',
        'https://support.xbox.com/help/games-apps/my-games-apps/all-about-pc-gaming',
        'https://www.xbox.com/en-us/games/store/xbox-game-pass-ultimate/cfq7ttc0khs0?icid=DSM_All_XboxGamePassUltimate',
        'https://www.xbox.com/en-us/games/store/pc-game-pass/cfq7ttc0kgq8?icid=CNavAllPCGamePass',
    ],
    'discovery_mechanisms_allowed': [
        'robots.txt declarations (fetched first, before any other request, on each host)',
        'sitemap documents declared in robots.txt, or the conventional /sitemap.xml path if none declared (same convention already used in Stage 10 for support.microsoft.com)',
        'same-host navigation links found in already-fetched page content (e.g. a "Consoles" menu item)',
    ],
    'discovery_mechanisms_forbidden': [
        'guessed product-slug URLs',
        'search engines',
        'Chromium / browser automation',
        'dealer/reseller sources',
        'brute-forcing model/SKU codes',
    ],
    'limits': {
        'max_requests_total': 16,
        'max_requests_per_host': 10,
        'max_hosts': 2,
        'max_response_bytes_per_request': 750_000,
        'min_interval_seconds_between_requests': 2.0,
        'timeout_seconds_per_request': 10.0,
        'max_sitemap_child_documents_per_host': 2,
        'max_candidate_links_followed_per_host': 4,
        'max_product_pages_deep_fetched': 2,
    },
    'pdf_document_budget_if_a_manual_is_found': {
        'note': 'A separate, explicit budget is declared in its own artifact (per Stage 8.6 convention) only if a same-host or otherwise-allowlisted manual/PDF URL is actually discovered -- never predeclared speculatively with an unbounded scope.',
        'reuses': 'product_tool.census logic proven in Stage 8.6 (fetch_document_bounded): Range-based chunked fetch, ETag/Last-Modified consistency check, complete/partial/unknown_completeness classification.',
    },
    'mechanism': 'product_tool.census.endpoint_probe.AccessProbe with ProbePolicy (max_bytes=750000, min_interval=2s, timeout=10s), allowed_hosts restricted to the two hosts above. Redirect chains are validated per-hop; an off-host redirect aborts that request rather than following it.',
    'robots_txt_policy': (
        'robots.txt for each host is fetched and parsed before any other request to that host. '
        'Disallow rules under User-agent: * (and the declared crawler UA if present) are '
        'honored for every subsequent path on that host; a disallowed candidate path is skipped, '
        'not fetched, and recorded as such.'
    ),
    'stop_conditions': [
        'max_requests_total or max_requests_per_host reached',
        'HTTP 403 on a host -> stop all further requests to that host for the remainder of this run',
        'HTTP 429 on a host -> stop all further requests to that host for the remainder of this run',
        'CAPTCHA or challenge signal detected on a host -> stop all further requests to that host',
        'robots.txt Disallow covering the only remaining candidate path on a host -> stop that host',
        'a redirect or discovered link points off the two allowed hosts -> recorded, not followed',
        'no further in-scope candidate links remain toward a console hardware product page',
    ],
    'explicit_non_goals': [
        'No Chromium / browser automation',
        'No search engines',
        'No dealer/reseller sources',
        'No brute-forcing of model codes or SKU/slug patterns',
        'No invented endpoints or guessed URLs',
        'No widening beyond the single selected catalog row (XXU-00015)',
        'No general Xbox census across other catalog rows',
        'No automatic promotion of either host into official_domains.v1.json or source_catalog.v2.json',
    ],
}

OUT.mkdir(parents=True, exist_ok=True)
(OUT / 'budget_predeclaration.json').write_text(json.dumps(budget, indent=2, ensure_ascii=False), encoding='utf-8')
print('budget written')
