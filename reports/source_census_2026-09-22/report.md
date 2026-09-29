# All-brand source census v2

Generated: 2026-09-21T21:30:17+00:00

## Coverage stages

- Catalog brands: 289
- Catalog market: unknown
- Researched brands (candidate evidence or deeper): 25
- Not researched (`research_pending`): 264
- Brands with domain candidate: 25 (62.1% of assortment)
- Brands with verified official domain: 25 (62.1%)
- Brands with checked homepage: 8 (34.5%)
- Brands with checked product page: 8 (34.5%)
- Brands with inspected search capability: 7 (32.3%)
- Brands with working search detected: 3 (13.1%)
- Brands with checked support: 7 (27.8%)
- Sources with confirmed challenge: 0
- Sources with suspected challenge: 3
- Sources requiring browser verification: 0
- Endpoints with confirmed challenge: 0
- Endpoints with suspected challenge: 14

- Sources with checked endpoints: 8 of 13
- Accessible checked endpoints: 32
- Blocked/rate-limited checked endpoints: 7

A known homepage alone is not counted as product coverage.

## Bounded source recheck

| Source | Homepage | Product | Support | Identity observations | Protection | Confirmed engines |
| --- | --- | --- | --- | ---: | --- | --- |
| bosch_home | 200:direct_access | 200:direct_access | 200:direct_access | 2 | ordinary_page | generic_json_ld_product, next_js |
| bosch_tools | 200:direct_access | 200:direct_access | — | 1 | ordinary_page | — |
| xiaomi_global | 200:javascript_required | 200:direct_access, 200:direct_access | 200:javascript_required | 2 | ordinary_page | generic_json_ld_product |
| samsung_kz | 200:direct_access | 200:direct_access | 200:direct_access, 200:direct_access | 3 | ordinary_page | adobe_experience_manager |
| apple_kz | 200:direct_access | 200:direct_access, 200:direct_access | — | 2 | ordinary_page | generic_json_ld_product |
| huawei_kz | 200:direct_access | 200:direct_access | 200:direct_access | 2 | challenge_suspected, ordinary_page | adobe_experience_manager |
| lenovo_kz | 200:direct_access | 403:captcha_or_blocked | 200:direct_access, 200:direct_access | 2 | challenge_suspected | generic_json_ld_product |
| gigabyte_global | 403:captcha_or_blocked | 403:captcha_or_blocked, 403:captcha_or_blocked | 403:captcha_or_blocked | 0 | challenge_suspected | — |

## Platform clusters

| Layer | Engine | Sources | Single source | Multi-site | Adapter candidate |
| --- | --- | ---: | --- | --- | --- |
| product_data | generic_json_ld_product | 4 | False | True | True |
| site_cms | adobe_experience_manager | 2 | False | True | False |
| site_cms | next_js | 1 | True | False | False |

## Custom or still unclassified sites

- bosch_tools
- gigabyte_global

## Browser or manual review

- xiaomi_global
- huawei_kz
- lenovo_kz
- gigabyte_global

## Next shared layer

Implement and harden generic sitemap, JSON-LD, embedded-state, search-capability and identity-validation primitives before any CMS-specific adapter. No multi-site platform cluster is assumed from a homepage fingerprint.
