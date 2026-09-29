"""Stage 10.1 -- research-only source profile, modeled on official_domains.v1.json's
schema, but written to this stage's own report directory only. Not merged into
product_tool/config/official_domains.v1.json and not executable. enabled=false,
research_enabled=false until this stage's own bounded probe confirms official content."""
import json
from pathlib import Path

OUT = Path(r'A:\work\dev\product_cards_mvp\reports\source_census_2026-09-23_stage10_1')
provenance = json.loads((OUT / 'offline_provenance.json').read_text(encoding='utf-8'))

profile = {
    'schema_version': 1,
    'usage': 'stage10_1_research_only; NOT merged into product_tool/config/official_domains.v1.json; no production promotion by this stage',
    'domains': [
        {
            'domain_id': 'microsoft_xbox_www_xbox_com_research',
            'source_family': 'microsoft',
            'brand': 'Microsoft',
            'url': 'https://www.xbox.com/',
            'market': 'unknown',
            'market_scope': 'unknown',
            'division': 'xbox',
            'category_scope': ['game_consoles'],
            'ownership_evidence': [
                {
                    'type': 'first_party_page_link',
                    'url': provenance['origin_page']['final_url_after_redirect'],
                    'verified_at': '2026-09-23',
                    'access_method': 'http_fetch_stage10',
                    'supports': 'Linked from support.microsoft.com\'s own confirmed-official global navigation as "XBOX" / "Shop XBOX"; not yet content-verified for this host itself.',
                },
            ],
            'page_hosts': ['www.xbox.com'],
            'support_hosts': [],
            'document_hosts': [],
            'capabilities': {
                'sitemap': 'not_checked',
                'search': 'not_checked',
                'catalog': 'not_checked',
            },
            'priority': None,
            'official_status': 'pending_verification',
            'enabled': False,
            'research_enabled': False,
            'access_status': 'not_checked',
            'protection_status': 'not_checked',
            'discovery_status': 'not_checked',
            'last_checked_at': '',
        },
        {
            'domain_id': 'microsoft_xbox_support_xbox_com_research',
            'source_family': 'microsoft',
            'brand': 'Microsoft',
            'url': 'https://support.xbox.com/',
            'market': 'unknown',
            'market_scope': 'unknown',
            'division': 'xbox',
            'category_scope': ['game_consoles'],
            'ownership_evidence': [
                {
                    'type': 'first_party_page_link',
                    'url': provenance['origin_page']['final_url_after_redirect'],
                    'verified_at': '2026-09-23',
                    'access_method': 'http_fetch_stage10',
                    'supports': 'Linked from support.microsoft.com\'s own confirmed-official global navigation as "Xbox"; subdomain naming parallels the already-verified support.microsoft.com; not yet content-verified for this host itself.',
                },
            ],
            'page_hosts': [],
            'support_hosts': ['support.xbox.com'],
            'document_hosts': [],
            'capabilities': {
                'sitemap': 'not_checked',
                'search': 'not_checked',
                'catalog': 'not_checked',
            },
            'priority': None,
            'official_status': 'pending_verification',
            'enabled': False,
            'research_enabled': False,
            'access_status': 'not_checked',
            'protection_status': 'not_checked',
            'discovery_status': 'not_checked',
            'last_checked_at': '',
        },
    ],
    'promotion_note': (
        'This file is a research artifact for Stage 10.1 only. Promoting either domain into '
        'product_tool/config/official_domains.v1.json (research registry) or, later, '
        'source_catalog.v2.json (production registry) is an explicit, separate, out-of-band '
        'decision -- not performed automatically by this stage regardless of probe outcome.'
    ),
}

(OUT / 'research_source_profile.json').write_text(json.dumps(profile, indent=2, ensure_ascii=False), encoding='utf-8')
print('written, domains:', len(profile['domains']))
