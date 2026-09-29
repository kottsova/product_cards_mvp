# All-brand source census v2

Generated: 2026-09-21T22:37:13+00:00

## Coverage stages

- Catalog brands: 289
- Catalog market: unknown
- Researched brands (candidate evidence or deeper): 51
- Not researched (`research_pending`): 238
- Brands with domain candidate: 51 (77.7% of assortment)
- Brands with verified official domain: 50 (77.2%)
- Brands with checked homepage: 25 (62.1%)
- Brands with checked product page: 20 (51.9%)
- Brands with inspected search capability: 24 (60.0%)
- Brands with working search detected: 15 (46.9%)
- Brands with checked support: 17 (36.7%)
- Brands endpoint-sampled: 25 (62.1%)
- Brands with product discovery validated: 17 (51.7%)
- Brands with exact identity validated: 6 (24.2%)
- Brands production-ready: 1 (3.4%)
- Sources with confirmed challenge: 2
- Sources with suspected challenge: 12
- Sources requiring browser verification: 0
- Endpoints with confirmed challenge: 4
- Endpoints with suspected challenge: 32

- Sources with checked endpoints: 25 of 56
- Accessible checked endpoints: 81
- Blocked/rate-limited checked endpoints: 14

A known homepage alone is not counted as product coverage.

The requested remainder listed 18 brand labels; POCO was already sampled through the shared `xiaomi_global` source, so 17 brands actually remained (LG plus 16 candidate records). All 25 previously domain-covered catalog brands now have endpoint evidence.

## Bounded source recheck

| Source | Homepage | Product | Support | Identity observations | Protection | Confirmed engines |
| --- | --- | --- | --- | ---: | --- | --- |
| lg_kz | 200:direct_access | 200:javascript_required | 200:direct_access | 2 | challenge_suspected, ordinary_page | adobe_experience_manager, next_js |
| bosch_home | 200:direct_access | 200:direct_access | 200:direct_access | 2 | ordinary_page | generic_json_ld_product, next_js |
| bosch_tools | 200:direct_access | 200:direct_access | — | 1 | ordinary_page | — |
| xiaomi_global | 200:javascript_required | 200:direct_access, 200:direct_access | — | 2 | ordinary_page | generic_json_ld_product |
| samsung_kz | 200:direct_access | 200:direct_access | 200:direct_access | 2 | ordinary_page | adobe_experience_manager |
| apple_kz | 200:direct_access | 200:direct_access, 200:direct_access | — | 2 | ordinary_page | generic_json_ld_product |
| huawei_kz | 200:direct_access | 200:direct_access | 200:direct_access | 2 | challenge_suspected, ordinary_page | adobe_experience_manager |
| lenovo_kz | 200:direct_access | 200:direct_access | 200:direct_access, 200:direct_access | 3 | challenge_suspected | generic_json_ld_product |
| gigabyte_global | 403:captcha_or_blocked | 403:captcha_or_blocked, 403:captcha_or_blocked | — | 0 | challenge_suspected | — |
| asus_global_candidate | 200:direct_access | — | 200:direct_access | 0 | challenge_suspected, inconclusive, ordinary_page | — |
| biryusa_ru_candidate | 200:direct_access | — | — | 0 | ordinary_page | — |
| msi_global_candidate | 403:captcha_or_blocked | 403:captcha_or_blocked | 403:captcha_or_blocked | 0 | challenge_suspected, ordinary_page | — |
| acer_global_candidate | —:unavailable | —:unavailable | —:unavailable | 0 | challenge_confirmed, inconclusive | — |
| tplink_global_candidate | 200:direct_access | 200:direct_access | 200:direct_access | 2 | challenge_suspected, ordinary_page | — |
| hp_global_candidate | 200:direct_access | — | 200:direct_access | 0 | challenge_suspected, inconclusive, ordinary_page | adobe_experience_manager |
| honor_global_candidate | 200:direct_access | 200:direct_access | 200:direct_access | 2 | ordinary_page | adobe_experience_manager |
| thermalright_global_candidate | 200:direct_access | 200:direct_access | — | 1 | challenge_suspected, ordinary_page | woocommerce |
| rombica_ru_candidate | 200:direct_access | — | — | 0 | inconclusive | — |
| silicon_power_global_candidate | 200:direct_access | — | — | 0 | inconclusive, ordinary_page | — |
| karcher_global_candidate | 200:direct_access | 200:direct_access | 404:unavailable | 1 | challenge_suspected, inconclusive, ordinary_page | generic_json_ld_product |
| infinix_global_candidate | 200:direct_access | 200:direct_access | 404:unavailable | 1 | inconclusive, ordinary_page | nuxt |
| jbl_global_candidate | 403:captcha_or_blocked | 403:captcha_or_blocked | 403:captcha_or_blocked | 0 | challenge_confirmed, ordinary_page | — |
| bequiet_global_candidate | 200:direct_access | 200:direct_access | 200:direct_access | 1 | challenge_suspected, inconclusive | — |
| patriot_memory_global_candidate | 200:direct_access | 200:direct_access | 404:unavailable | 1 | inconclusive, ordinary_page | next_js |
| logitech_global_candidate | 200:direct_access | 403:captcha_or_blocked | 200:direct_access | 0 | challenge_suspected, ordinary_page | adobe_experience_manager |

## Platform clusters

| Layer | Engine | Sources | Single source | Multi-site | Adapter candidate |
| --- | --- | ---: | --- | --- | --- |
| product_data | generic_json_ld_product | 5 | False | True | False |
| site_cms | adobe_experience_manager | 6 | False | True | False |
| site_cms | next_js | 3 | False | True | False |
| commerce_search | woocommerce | 1 | True | False | False |
| site_cms | nuxt | 1 | True | False | False |

## JSON-LD Product field coverage

| Source | name | sku | mpn | model | gtin | brand | image | description | characteristics | documents | variants | exact identity |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| bosch_home | yes | no | yes | no | yes | yes | yes | yes | yes | no | no | True |
| xiaomi_global | yes | no | no | no | no | yes | yes | yes | no | no | no | True |
| apple_kz | yes | no | no | no | no | yes | yes | yes | no | no | no | True |
| lenovo_kz | yes | yes | yes | no | no | yes | yes | no | no | no | no | True |
| karcher_global_candidate | yes | yes | yes | no | no | yes | yes | yes | no | no | no | True |

## Remaining research_pending

GEFEST, Irbis, KingBank, Raskat, YOSHIRO, ASRock, OCYPUS, SANDISK, 1stPlayer, DON, NINTENDO, KingDian, Palit, Beats, Dell, BenQ, Microsoft, NETAC, TECNO, SAMA, DxRacer, THERMALTAKE, Weissgauff, Dreame, XPG, GoPro, HYPERX, Iiyama, PocketBook, ZOTAC, Tefal, EVGA, metabo, WD, Sony, ОРСК, Colorful, Pantum, NEC, BQ., GAMEMAX, Gorenje, Lyambda, Super Flower, Accesstyle, AeroCool, GamerStorm, Corsair, Dahua, JONSBO, Haylou, NZXT, Deerma, Makita, Realme, Teamgroup, ViewSonic, Wacom, Wahoo, Ecovacs, GENIUS, Skullcandy, Zalman, Dunobil, Brother, Crucial, Ezviz, Sjcam, 70MAI, iFrogz, Maxsun, Ninebot By Segway, Nokia, PNY, TCL, 1More, Colmi, HiLook, iconBIT, Netcraze, СНТ, ANYCUBIC, Playme, POLARIS, roborock, НРЗ, APC, HAVN, JVC, Sapphire, SUDIO, ZTE, Каркам, Huion, Oral-B, TRONSMART, Epson, Buro, janome, Seagate, SEASONIC, XP-PEN, Creality, deWalt, ELARI, JAM, MARSHALL, Meizu, NETIS, Braven, HIKVISION, HYUNDAI, KitchenAid, Mercusys, MIKROTIK, Singer, 2018 FIFA World Cup Russia™, Apacer, Inno3D, PHILIPS Avent, Smartmi, Thomas, XPPEN, Aqara, Biostar, Cooler Master, D-LINK, HuntKey, Kyocera, Mophie, ONYX BOOX, PowerColor, Steelseries, Team Group, Toshiba, Transcend, Ugreen, XFX, ACD, Dji, DOOGEE, EnerMax, Evapolar, HTC, IK Multimedia, Micromax, Moulinex, NEWLAND, Roidmi, Valve, Western Digital, Kingspec, MOSHI, Tenda, Texet, URBANEARS, WHIRLPOOL, X-Game, Xerox, 3Logic Lime, ADVOCAM, agi, APNX, ASUSTOR, Cozistyle, DELI, Fly,, Fractal, HAIER, Hysure, ITEL, Jabra, Kenwood, Lab.c, Logitech G, maibenben, Powercom, Xclea, Alienware, CARCAM, Doni, F+, FlashForge, Foxline, Jeton, Jimmy, Omthing, POWERMAN, SATECHI, VIVO, Xencelabs, ИМПУЛЬС, ACD Lime, AEG, Bookeen, COUGAR, Griffin, HISENSE, HiWatch, HUTT, Intego, Kyvol, Lebooo, Liebherr, Lite-on, Microtek, RODE, TOTOLINK, ZMI, ZyXEL, СТН, 360, 360 Robot Vacuum Cleaner, AFOX, BORK, CyberPower, Fujitsu, Hansa, Harman Kardon, Hercules, Hotpoint-Ariston, HP (Hewlett Packard), KENU, Lexmark, MERTECH, Motorola, NATIONAL, NINETYGO, QNAP, QUMAN, Qumann, Speck, TrendVision, VESTEL, viomi, Xiaom, XP, Zanussi

## Custom or still unclassified sites

- bosch_tools
- gigabyte_global
- asus_global_candidate
- biryusa_ru_candidate
- msi_global_candidate
- acer_global_candidate
- tplink_global_candidate
- rombica_ru_candidate
- silicon_power_global_candidate
- jbl_global_candidate
- bequiet_global_candidate

## Browser or manual review

- lg_kz
- xiaomi_global
- huawei_kz
- lenovo_kz
- gigabyte_global
- asus_global_candidate
- msi_global_candidate
- acer_global_candidate
- tplink_global_candidate
- hp_global_candidate
- thermalright_global_candidate
- karcher_global_candidate
- jbl_global_candidate
- bequiet_global_candidate
- logitech_global_candidate

## Next shared layer

Implement a shared bounded discovery orchestration layer around sitemap/catalog indexes, internal-search evidence, embedded state and exact-identity validation. Do not implement a generic JSON-LD adapter yet: the sampled sites share `Product` markup but not a validated identifier/variant structure. No CMS-specific adapter is justified by the present evidence.

## Changes in this stage

- Canonicalized executable configuration on `source_catalog.v2.json`; removed unreferenced v1 catalog/schema files and made the loader v2-only.
- Replaced Sulpak category-group inference with an exact five-category allowlist plus explicit review and deny rules.
- Added persisted candidate endpoint records, per-source checkpoints, five independent confirmation levels, final URLs, JSON-LD field coverage, embedded-state kinds and discovery evidence.
- Added bounded targets for all previously domain-covered brands and added the next official-domain batch; HIPER remains an unverified candidate and ATLANT supplies the 50th verified brand.
- Downgraded generic JSON-LD structure compatibility and withheld adapter recommendation where useful identity/variant fields do not converge.
- Preserved LG adapters and storage compatibility; no database migration or production adapter was introduced.

## Verification

- Schema, status, fingerprint, allowlist and safe-probe regressions are covered by `tests/test_source_census_v2.py` and the full test suite.
- `python -m unittest discover -s tests -v`: 78 tests passed, 0 failures (2026-09-22).
- Both canonical JSON documents validate against their JSON Schema files.
