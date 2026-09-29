# Stage 7.1: catalog-backed identity reconciliation

Stage 7 remains an immutable baseline. The original `Товары` rows were read with openpyxl read_only=True; no workbook writes occurred. Alternate titles remain titles, not alternate codes. No alternate-code column exists in this catalog.

## Results

- Products: 11. Previous not-found decisions changed: 6/6.
- Exact model/variant: 0. Incomplete: 10. Identity review: RLD35GD.
- New HTTP: 8/24; replay HTTP: 0; Chromium: 0; dealer requests: 0; dealer gates enabled: 0.
- Reused baseline snapshots: 84; new snapshots: 8; unique official candidate URLs: 65.
- Candidate occurrences after reranking: {'unvalidated': 112, 'conflict': 2, 'insufficient': 16}. Occurrences across products/domains are not unique pages.

A received HTTP 200 is recorded separately from evidence of a completed product search. Empty/JavaScript search shells, truncated sitemap traversal, missing responses and pending product candidates keep the result incomplete. `not_found` is never inherited from Stage 7. Structured Product names can confirm a title-derived marketing model only under matching brand/category, token boundaries and non-conflicting model/variant evidence. Generic body text cannot confirm identity.

## Per-product audit

| Seller SKU | Real catalog title | Before | After | New HTTP | Dealer |
|---|---|---|---|---:|---|
| F2J3HS0W | Стиральная машина F2J3HS0W | official_exact_product_not_found | official_search_incomplete | 0 | closed |
| A9K-PRO1 | Вертикальный пылесос LG A9K-PRO1 | official_exact_product_not_found | official_search_incomplete | 0 | closed |
| SBV45FX01R | Полновстраиваемая посудомоечная машина SBV45FX01R | official_search_incomplete | official_search_incomplete | 0 | closed |
| CMG633BB1 | Встраиваемый электрический духовой шкаф Bosch CMG633BB1 | official_search_incomplete | official_search_incomplete | 0 | closed |
| MNA114MS1CCX | Телевизор MNA114MS1CCX/114"/UHD/Smart TV/Wi-Fi/BT | official_exact_product_not_found | official_search_incomplete | 0 | closed |
| Jet_70_turbo/(VS15T7031R4/EV) | Пылесос Jet 70 Turbo VS15T7031R4/EV | official_search_incomplete | official_search_incomplete | 4 | closed |
| 1.055-701.0 | Электрошвабра FC 7 Cordless, 1.055-701.0 | official_exact_product_not_found | official_search_incomplete | 2 | closed |
| 1.633-426.0 | Мойщик окон WV 2 Black Edition, 1.633-426.0 | official_exact_product_not_found | official_search_incomplete | 2 | closed |
| HHR12A | Беспроводной вертикальный моющий пылесос G10, HHR12A | official_search_incomplete | official_search_incomplete | 0 | closed |
| RLD35GD | Робот-пылесос D20 Plus с влажной уборкой<br>Робот-пылесос Robot Vacuum моющий D20 Plus, RLD35GD | official_search_incomplete | identity_review_required | 0 | closed |
| WD10T654CBH/LD | Стирально-сушильная машина WD10T654CBH/LD | official_exact_product_not_found | official_search_incomplete | 0 | closed |

### F2J3HS0W

- Catalog rows: Товары!A8775:H8775
- Identity status: reconciled
- Original title(s): Стиральная машина F2J3HS0W
- Brand/category: LG / Стиральные машины
- Alternate code: None
- Variants: {}
- Candidates: F2J3HS0W → manufacturer_model (title_raw, confidence 0.98, brand.lg.model); F2J3HS0W → seller_sku (seller_sku_raw, confidence 0.7, catalog_field)
- Planned queries: F2J3HS0W
- High-confidence identity query scope complete: False
- Dealer gate: official_search_not_complete_or_exact_found

| Official domain | Executed/replayed queries and evidence | Snapshots | Candidate outcomes |
|---|---|---:|---|
| lg_kz | F2J3HS0W: snapshot_replay, HTTP response=True, checked=False | 6 | {} |
| lg_global | F2J3HS0W: not_executed, HTTP response=False, checked=False | 5 | {} |
| lg_us | F2J3HS0W: not_executed, HTTP response=False, checked=False | 5 | {} |
| lg_kr | F2J3HS0W: snapshot_replay, HTTP response=True, checked=False | 6 | {} |

No official product candidates were supported by the bounded saved evidence.

### A9K-PRO1

- Catalog rows: Товары!A8723:H8723
- Identity status: reconciled
- Original title(s): Вертикальный пылесос LG A9K-PRO1
- Brand/category: LG / Пылесосы
- Alternate code: None
- Variants: {}
- Candidates: A9K-PRO1 → manufacturer_model (title_raw, confidence 0.98, brand.lg.model); A9K-PRO1 → seller_sku (seller_sku_raw, confidence 0.7, catalog_field)
- Planned queries: A9K-PRO1
- High-confidence identity query scope complete: False
- Dealer gate: official_search_not_complete_or_exact_found

| Official domain | Executed/replayed queries and evidence | Snapshots | Candidate outcomes |
|---|---|---:|---|
| lg_kz | A9K-PRO1: snapshot_replay, HTTP response=True, checked=False | 7 | {} |
| lg_global | A9K-PRO1: not_executed, HTTP response=False, checked=False | 5 | {} |
| lg_us | A9K-PRO1: not_executed, HTTP response=False, checked=False | 5 | {} |
| lg_kr | A9K-PRO1: snapshot_replay, HTTP response=True, checked=False | 7 | {} |

No official product candidates were supported by the bounded saved evidence.

### SBV45FX01R

- Catalog rows: Товары!A3317:H3317
- Identity status: reconciled
- Original title(s): Полновстраиваемая посудомоечная машина SBV45FX01R
- Brand/category: BOSCH / Машины посудомоечные
- Alternate code: None
- Variants: {}
- Candidates: SBV45FX01R → manufacturer_model (title_raw, confidence 0.98, brand.bosch.model); SBV45FX01R → seller_sku (seller_sku_raw, confidence 0.7, catalog_field)
- Planned queries: SBV45FX01R
- High-confidence identity query scope complete: False
- Dealer gate: official_search_not_complete_or_exact_found

| Official domain | Executed/replayed queries and evidence | Snapshots | Candidate outcomes |
|---|---|---:|---|
| bosch_global | SBV45FX01R: not_executed, HTTP response=False, checked=False | 5 | {} |
| bosch_de | SBV45FX01R: not_executed, HTTP response=False, checked=False | 5 | {} |
| bosch_uk | SBV45FX01R: not_executed, HTTP response=False, checked=False | 8 | {'unvalidated': 13, 'conflict': 1, 'insufficient': 2} |

Official candidates (URL → final identity level):

- https://www.bosch-home.co.uk/en/product/small-appliances/airfryer/airfryerdoubledrawer/MAFD661B0G → unvalidated
- https://www.bosch-home.co.uk/en/product/small-appliances/airfryer/airfryerdoubledrawer/MAFD661B0G?intcid=Home_DoubleStack_Jul26 → conflict
- https://www.bosch-home.co.uk/products/cooking-baking/cooker-hoods/hoods-product-advisor?intcid=OPA_HoodFinder~~Website~ContentTeaser~ → unvalidated
- https://www.bosch-home.co.uk/products/cooking-baking/hobs/hobs-product-advisor?intcid=OPA_HobFinder~~Website~ContentTeaser~ → unvalidated
- https://www.bosch-home.co.uk/products/cooking-baking/ovens-product-advice?intcid=OPA_OvenAndCookerFinder~~Website~ContentTeaser~ → unvalidated
- https://www.bosch-home.co.uk/products/dishwashers/dishwasher-product-advice?intcid=OPA_DishwasherFinder~~Website~ContentTeaser~ → unvalidated
- https://www.bosch-home.co.uk/products/fridges-freezers/fridge-freezer-split-ratio?intcid=qcn_washerdryers_categoryPage_dec25 → insufficient
- https://www.bosch-home.co.uk/products/fridges-freezers/fridgefreezer-product-advice?intcid=OPA_FrenchDoor_PLP_Nov24 → unvalidated
- https://www.bosch-home.co.uk/products/fridges-freezers/fridgefreezer-product-advice?intcid=OPA_FridgeFinder~~Website~ContentTeaser~ → unvalidated
- https://www.bosch-home.co.uk/products/online-product-advisor → unvalidated
- https://www.bosch-home.co.uk/products/online-product-advisor?intcid=ProductFinder_OnlineProductAdvisor_nov25 → insufficient
- https://www.bosch-home.co.uk/products/spare-parts → unvalidated
- https://www.bosch-home.co.uk/products/vacuum-cleaners/cordless-vacuum-cleaners/unlimited-10?intcid=home_stagebanner_unlimited10_oct24 → unvalidated
- https://www.bosch-home.co.uk/products/vacuum-cleaners/vacuum-cleaner-product-advisor?intcid=OPA_VacuumFinder~~Website~ContentTeaser~ → unvalidated
- https://www.bosch-home.co.uk/products/washers-dryers/laundry-product-advice?intcid=OPA_WashingMachineFinder~~Website~ContentTeaser~ → unvalidated
- https://www.bosch-home.co.uk/products/washers-dryers/tumble-dryer-product-advisor?intcid=OPA_TumbleDryerProductFinder~~Website~ContentTeaser~ → unvalidated

### CMG633BB1

- Catalog rows: Товары!A3173:H3173
- Identity status: reconciled
- Original title(s): Встраиваемый электрический духовой шкаф Bosch CMG633BB1
- Brand/category: BOSCH / Духовые шкафы
- Alternate code: None
- Variants: {}
- Candidates: CMG633BB1 → manufacturer_model (title_raw, confidence 0.98, brand.bosch.model); CMG633BB1 → seller_sku (seller_sku_raw, confidence 0.7, catalog_field)
- Planned queries: CMG633BB1
- High-confidence identity query scope complete: False
- Dealer gate: official_search_not_complete_or_exact_found

| Official domain | Executed/replayed queries and evidence | Snapshots | Candidate outcomes |
|---|---|---:|---|
| bosch_global | CMG633BB1: not_executed, HTTP response=False, checked=False | 5 | {} |
| bosch_de | CMG633BB1: not_executed, HTTP response=False, checked=False | 5 | {} |
| bosch_uk | CMG633BB1: not_executed, HTTP response=False, checked=False | 8 | {'unvalidated': 13, 'conflict': 1, 'insufficient': 2} |

Official candidates (URL → final identity level):

- https://www.bosch-home.co.uk/en/product/small-appliances/airfryer/airfryerdoubledrawer/MAFD661B0G → unvalidated
- https://www.bosch-home.co.uk/en/product/small-appliances/airfryer/airfryerdoubledrawer/MAFD661B0G?intcid=Home_DoubleStack_Jul26 → conflict
- https://www.bosch-home.co.uk/products/cooking-baking/cooker-hoods/hoods-product-advisor?intcid=OPA_HoodFinder~~Website~ContentTeaser~ → unvalidated
- https://www.bosch-home.co.uk/products/cooking-baking/hobs/hobs-product-advisor?intcid=OPA_HobFinder~~Website~ContentTeaser~ → unvalidated
- https://www.bosch-home.co.uk/products/cooking-baking/ovens-product-advice?intcid=OPA_OvenAndCookerFinder~~Website~ContentTeaser~ → unvalidated
- https://www.bosch-home.co.uk/products/dishwashers/dishwasher-product-advice?intcid=OPA_DishwasherFinder~~Website~ContentTeaser~ → unvalidated
- https://www.bosch-home.co.uk/products/fridges-freezers/fridge-freezer-split-ratio?intcid=qcn_washerdryers_categoryPage_dec25 → insufficient
- https://www.bosch-home.co.uk/products/fridges-freezers/fridgefreezer-product-advice?intcid=OPA_FrenchDoor_PLP_Nov24 → unvalidated
- https://www.bosch-home.co.uk/products/fridges-freezers/fridgefreezer-product-advice?intcid=OPA_FridgeFinder~~Website~ContentTeaser~ → unvalidated
- https://www.bosch-home.co.uk/products/online-product-advisor → unvalidated
- https://www.bosch-home.co.uk/products/online-product-advisor?intcid=ProductFinder_OnlineProductAdvisor_nov25 → insufficient
- https://www.bosch-home.co.uk/products/spare-parts → unvalidated
- https://www.bosch-home.co.uk/products/vacuum-cleaners/cordless-vacuum-cleaners/unlimited-10?intcid=home_stagebanner_unlimited10_oct24 → unvalidated
- https://www.bosch-home.co.uk/products/vacuum-cleaners/vacuum-cleaner-product-advisor?intcid=OPA_VacuumFinder~~Website~ContentTeaser~ → unvalidated
- https://www.bosch-home.co.uk/products/washers-dryers/laundry-product-advice?intcid=OPA_WashingMachineFinder~~Website~ContentTeaser~ → unvalidated
- https://www.bosch-home.co.uk/products/washers-dryers/tumble-dryer-product-advisor?intcid=OPA_TumbleDryerProductFinder~~Website~ContentTeaser~ → unvalidated

### MNA114MS1CCX

- Catalog rows: Товары!A12665:H12665
- Identity status: reconciled
- Original title(s): Телевизор MNA114MS1CCX/114"/UHD/Smart TV/Wi-Fi/BT
- Brand/category: Samsung / Телевизоры
- Alternate code: None
- Variants: {'screen_size': '114'}
- Candidates: MNA114MS1CCX → manufacturer_model (title_raw, confidence 0.98, brand.samsung.model); MNA114MS1CCX → seller_sku (seller_sku_raw, confidence 0.7, catalog_field)
- Planned queries: MNA114MS1CCX
- High-confidence identity query scope complete: False
- Dealer gate: official_search_not_complete_or_exact_found

| Official domain | Executed/replayed queries and evidence | Snapshots | Candidate outcomes |
|---|---|---:|---|
| samsung_kz | MNA114MS1CCX: snapshot_replay, HTTP response=True, checked=False | 6 | {} |
| samsung_us | MNA114MS1CCX: snapshot_replay, HTTP response=True, checked=False | 4 | {} |
| samsung_kr | MNA114MS1CCX: not_executed, HTTP response=False, checked=False | 5 | {} |

No official product candidates were supported by the bounded saved evidence.

### Jet_70_turbo/(VS15T7031R4/EV)

- Catalog rows: Товары!A12193:H12193
- Identity status: reconciled
- Original title(s): Пылесос Jet 70 Turbo VS15T7031R4/EV
- Brand/category: Samsung / Пылесосы
- Alternate code: None
- Variants: {'region': 'EV'}
- Candidates: VS15T7031R4/EV → regional_model (title_raw, confidence 0.98, brand.samsung.model); Jet 70 Turbo → marketing_model (title_raw, confidence 0.98, brand.samsung.marketing); Jet_70_turbo/(VS15T7031R4/EV) → seller_sku (seller_sku_raw, confidence 0.7, catalog_field)
- Planned queries: VS15T7031R4/EV; JET 70 TURBO
- High-confidence identity query scope complete: False
- Dealer gate: official_search_not_complete_or_exact_found

| Official domain | Executed/replayed queries and evidence | Snapshots | Candidate outcomes |
|---|---|---:|---|
| samsung_kz | VS15T7031R4/EV: stage7_1_snapshot_replay, HTTP response=True, checked=False; JET 70 TURBO: stage7_1_snapshot_replay, HTTP response=True, checked=False | 8 | {} |
| samsung_us | VS15T7031R4/EV: stage7_1_snapshot_replay, HTTP response=True, checked=False; JET 70 TURBO: stage7_1_snapshot_replay, HTTP response=True, checked=False | 6 | {} |
| samsung_kr | VS15T7031R4/EV: not_executed, HTTP response=False, checked=False; JET 70 TURBO: not_executed, HTTP response=False, checked=False | 5 | {} |

No official product candidates were supported by the bounded saved evidence.

### 1.055-701.0

- Catalog rows: Товары!A7797:H7797
- Identity status: reconciled
- Original title(s): Электрошвабра FC 7 Cordless, 1.055-701.0
- Brand/category: Karcher / Пылесосы
- Alternate code: None
- Variants: {}
- Candidates: 1.055-701.0 → manufacturer_model (title_raw, confidence 0.98, brand.karcher.model); FC 7 Cordless → marketing_model (title_raw, confidence 0.98, brand.karcher.marketing); 1.055-701.0 → seller_sku (seller_sku_raw, confidence 0.7, catalog_field)
- Planned queries: 1.055-701.0; FC 7 CORDLESS
- High-confidence identity query scope complete: False
- Dealer gate: official_search_not_complete_or_exact_found

| Official domain | Executed/replayed queries and evidence | Snapshots | Candidate outcomes |
|---|---|---:|---|
| karcher_kz | 1.055-701.0: snapshot_replay, HTTP response=True, checked=False; FC 7 CORDLESS: stage7_1_snapshot_replay, HTTP response=True, checked=False | 8 | {} |
| karcher_global | 1.055-701.0: snapshot_replay, HTTP response=True, checked=False; FC 7 CORDLESS: stage7_1_snapshot_replay, HTTP response=True, checked=False | 8 | {} |
| karcher_de | 1.055-701.0: not_executed, HTTP response=False, checked=False; FC 7 CORDLESS: not_executed, HTTP response=False, checked=False | 5 | {} |

No official product candidates were supported by the bounded saved evidence.

### 1.633-426.0

- Catalog rows: Товары!A7910:H7910
- Identity status: reconciled
- Original title(s): Мойщик окон WV 2 Black Edition, 1.633-426.0
- Brand/category: Karcher / Стеклоочистители электрические
- Alternate code: None
- Variants: {'color': 'BLACK'}
- Candidates: 1.633-426.0 → manufacturer_model (title_raw, confidence 0.98, brand.karcher.model); WV 2 Black Edition → marketing_model (title_raw, confidence 0.98, brand.karcher.marketing); 1.633-426.0 → seller_sku (seller_sku_raw, confidence 0.7, catalog_field)
- Planned queries: 1.633-426.0; WV 2 BLACK EDITION
- High-confidence identity query scope complete: False
- Dealer gate: official_search_not_complete_or_exact_found

| Official domain | Executed/replayed queries and evidence | Snapshots | Candidate outcomes |
|---|---|---:|---|
| karcher_kz | 1.633-426.0: snapshot_replay, HTTP response=True, checked=False; WV 2 BLACK EDITION: stage7_1_snapshot_replay, HTTP response=True, checked=False | 8 | {} |
| karcher_global | 1.633-426.0: snapshot_replay, HTTP response=True, checked=False; WV 2 BLACK EDITION: stage7_1_snapshot_replay, HTTP response=True, checked=False | 8 | {} |
| karcher_de | 1.633-426.0: not_executed, HTTP response=False, checked=False; WV 2 BLACK EDITION: not_executed, HTTP response=False, checked=False | 5 | {} |

No official product candidates were supported by the bounded saved evidence.

### HHR12A

- Catalog rows: Товары!A4647:H4647
- Identity status: reconciled
- Original title(s): Беспроводной вертикальный моющий пылесос G10, HHR12A
- Brand/category: Dreame / Пылесосы
- Alternate code: None
- Variants: {}
- Candidates: HHR12A → possible_internal_code (title_raw, confidence 0.65, brand.dreame.model); G10 → marketing_model (title_raw, confidence 0.98, brand.dreame.marketing); HHR12A → seller_sku (seller_sku_raw, confidence 0.7, catalog_field)
- Planned queries: HHR12A; G10
- High-confidence identity query scope complete: False
- Dealer gate: official_search_not_complete_or_exact_found

| Official domain | Executed/replayed queries and evidence | Snapshots | Candidate outcomes |
|---|---|---:|---|
| dreame_global | HHR12A: not_executed, HTTP response=False, checked=False; G10: not_executed, HTTP response=False, checked=False | 8 | {'insufficient': 3, 'unvalidated': 22} |
| dreame_us | HHR12A: not_executed, HTTP response=False, checked=False; G10: not_executed, HTTP response=False, checked=False | 0 | {} |
| dreame_de | HHR12A: not_executed, HTTP response=False, checked=False; G10: not_executed, HTTP response=False, checked=False | 7 | {'unvalidated': 21, 'insufficient': 3} |

Official candidates (URL → final identity level):

- https://global.dreametech.com/products/a2 → insufficient
- https://global.dreametech.com/products/aero-straight-pro → insufficient
- https://global.dreametech.com/products/air-auto → insufficient
- https://global.dreametech.com/products/airstyle-era-2 → unvalidated
- https://global.dreametech.com/products/airstyle-pro-2 → unvalidated
- https://global.dreametech.com/products/anti → unvalidated
- https://global.dreametech.com/products/aurasteam-straight → unvalidated
- https://global.dreametech.com/products/coffee-master → unvalidated
- https://global.dreametech.com/products/d10s-plus → unvalidated
- https://global.dreametech.com/products/d20-air → unvalidated
- https://global.dreametech.com/products/d20-air-plus → unvalidated
- https://global.dreametech.com/products/d30-ultra → unvalidated
- https://global.dreametech.com/products/d30-ultra-black → unvalidated
- https://global.dreametech.com/products/dd20 → unvalidated
- https://global.dreametech.com/products/dreame-c1 → unvalidated
- https://global.dreametech.com/products/dreame-c1-station → unvalidated
- https://global.dreametech.com/products/dreame-h12-pro → unvalidated
- https://global.dreametech.com/products/dreame-h12-pro-flexreach → unvalidated
- https://global.dreametech.com/products/dreame-h15-pro → unvalidated
- https://global.dreametech.com/products/dreame-h15-pro-heat → unvalidated
- https://global.dreametech.com/products/dreame-rotafly-steamer-p7 → unvalidated
- https://global.dreametech.com/products/dreame-x50-ultra-complete → unvalidated
- https://global.dreametech.com/products/dreametv-s100 → unvalidated
- https://global.dreametech.com/products/dz40-pro → unvalidated
- https://global.dreametech.com/products/dz401-pro → unvalidated
- https://de.dreametech.com/products/dreame-g10-pro-nass-und-trockensauger → unvalidated
- https://de.dreametech.com/products/a2 → insufficient
- https://de.dreametech.com/products/aqua10-roller-saugroboter → insufficient
- https://de.dreametech.com/products/d10-plus-gen-2 → insufficient
- https://de.dreametech.com/products/d20-pro-plus-saugroboter → unvalidated
- https://de.dreametech.com/products/d20-saugroboter → unvalidated
- https://de.dreametech.com/products/dreame-aqua10-ultra-roller-complete-schwarz-saugroboter → unvalidated
- https://de.dreametech.com/products/dreame-aqua10-ultra-track-complete-saugroboter → unvalidated
- https://de.dreametech.com/products/dreame-aqua20-pro-ultra-roller-x-complete-schwarz-saugroboter → unvalidated
- https://de.dreametech.com/products/dreame-aura-mini-led-4k-tv-s100-65 → unvalidated
- https://de.dreametech.com/products/dreame-d20-air-plus-saugroboter → unvalidated
- https://de.dreametech.com/products/dreame-d30-ultra-saugroboter → unvalidated
- https://de.dreametech.com/products/dreame-dz40-pro-vollintegrierter-geschirrspuler → unvalidated
- https://de.dreametech.com/products/dreame-dz401-pro-freistehender-geschirrspuler → unvalidated
- https://de.dreametech.com/products/dreame-dz60-pro-vollintegrierter-geschirrspuler → unvalidated
- https://de.dreametech.com/products/dreame-ez60-pro-brucken-induktionskochfeld → unvalidated
- https://de.dreametech.com/products/dreame-fizzfresh-multi-door-kuhlschrank → unvalidated
- https://de.dreametech.com/products/dreame-h11-core-nass-und-trockensauger → unvalidated
- https://de.dreametech.com/products/dreame-h12-pro-flexlite-nass-und-trockensauger → unvalidated
- https://de.dreametech.com/products/dreame-h12-pro-flexreach → unvalidated
- https://de.dreametech.com/products/dreame-h13-pro → unvalidated
- https://de.dreametech.com/products/dreame-h14-ae-nass-und-trockensauger → unvalidated
- https://de.dreametech.com/products/dreame-h14-dual-nass-und-trockensauger → unvalidated
- https://de.dreametech.com/products/dreame-h15-mix-nass-und-trockensauger → unvalidated

### RLD35GD

- Catalog rows: Товары!A4669:H4669
- Identity status: ambiguous_catalog_identity
- Original title(s): Робот-пылесос D20 Plus с влажной уборкой / Робот-пылесос Robot Vacuum моющий D20 Plus, RLD35GD
- Brand/category: Dreame / Роботы-пылесосы
- Alternate code: None
- Variants: {}
- Candidates: D20 Plus → marketing_model (title_raw, confidence 0.98, brand.dreame.marketing); RLD35GD → possible_internal_code (alternate_titles_raw, confidence 0.65, brand.dreame.model); D20 Plus → marketing_model (alternate_titles_raw, confidence 0.98, brand.dreame.marketing); RLD35GD → seller_sku (seller_sku_raw, confidence 0.7, catalog_field)
- Planned queries: RLD35GD; D20 PLUS
- High-confidence identity query scope complete: False
- Dealer gate: official_search_not_complete_or_exact_found

| Official domain | Executed/replayed queries and evidence | Snapshots | Candidate outcomes |
|---|---|---:|---|
| dreame_global | RLD35GD: not_executed, HTTP response=False, checked=False; D20 PLUS: not_executed, HTTP response=False, checked=False | 8 | {'insufficient': 3, 'unvalidated': 22} |
| dreame_us | RLD35GD: not_executed, HTTP response=False, checked=False; D20 PLUS: not_executed, HTTP response=False, checked=False | 0 | {} |
| dreame_de | RLD35GD: not_executed, HTTP response=False, checked=False; D20 PLUS: not_executed, HTTP response=False, checked=False | 7 | {'insufficient': 3, 'unvalidated': 21} |

Official candidates (URL → final identity level):

- https://global.dreametech.com/products/a2 → insufficient
- https://global.dreametech.com/products/aero-straight-pro → insufficient
- https://global.dreametech.com/products/air-auto → insufficient
- https://global.dreametech.com/products/airstyle-era-2 → unvalidated
- https://global.dreametech.com/products/airstyle-pro-2 → unvalidated
- https://global.dreametech.com/products/anti → unvalidated
- https://global.dreametech.com/products/aurasteam-straight → unvalidated
- https://global.dreametech.com/products/coffee-master → unvalidated
- https://global.dreametech.com/products/d10s-plus → unvalidated
- https://global.dreametech.com/products/d20-air → unvalidated
- https://global.dreametech.com/products/d20-air-plus → unvalidated
- https://global.dreametech.com/products/d30-ultra → unvalidated
- https://global.dreametech.com/products/d30-ultra-black → unvalidated
- https://global.dreametech.com/products/dd20 → unvalidated
- https://global.dreametech.com/products/dreame-c1 → unvalidated
- https://global.dreametech.com/products/dreame-c1-station → unvalidated
- https://global.dreametech.com/products/dreame-h12-pro → unvalidated
- https://global.dreametech.com/products/dreame-h12-pro-flexreach → unvalidated
- https://global.dreametech.com/products/dreame-h15-pro → unvalidated
- https://global.dreametech.com/products/dreame-h15-pro-heat → unvalidated
- https://global.dreametech.com/products/dreame-rotafly-steamer-p7 → unvalidated
- https://global.dreametech.com/products/dreame-x50-ultra-complete → unvalidated
- https://global.dreametech.com/products/dreametv-s100 → unvalidated
- https://global.dreametech.com/products/dz40-pro → unvalidated
- https://global.dreametech.com/products/dz401-pro → unvalidated
- https://de.dreametech.com/products/a2 → insufficient
- https://de.dreametech.com/products/aqua10-roller-saugroboter → insufficient
- https://de.dreametech.com/products/d10-plus-gen-2 → insufficient
- https://de.dreametech.com/products/d20-pro-plus-saugroboter → unvalidated
- https://de.dreametech.com/products/d20-saugroboter → unvalidated
- https://de.dreametech.com/products/dreame-aqua10-ultra-roller-complete-schwarz-saugroboter → unvalidated
- https://de.dreametech.com/products/dreame-aqua10-ultra-track-complete-saugroboter → unvalidated
- https://de.dreametech.com/products/dreame-aqua20-pro-ultra-roller-x-complete-schwarz-saugroboter → unvalidated
- https://de.dreametech.com/products/dreame-aura-mini-led-4k-tv-s100-65 → unvalidated
- https://de.dreametech.com/products/dreame-d20-air-plus-saugroboter → unvalidated
- https://de.dreametech.com/products/dreame-d30-ultra-saugroboter → unvalidated
- https://de.dreametech.com/products/dreame-dz40-pro-vollintegrierter-geschirrspuler → unvalidated
- https://de.dreametech.com/products/dreame-dz401-pro-freistehender-geschirrspuler → unvalidated
- https://de.dreametech.com/products/dreame-dz60-pro-vollintegrierter-geschirrspuler → unvalidated
- https://de.dreametech.com/products/dreame-ez60-pro-brucken-induktionskochfeld → unvalidated
- https://de.dreametech.com/products/dreame-fizzfresh-multi-door-kuhlschrank → unvalidated
- https://de.dreametech.com/products/dreame-g10-pro-nass-und-trockensauger → unvalidated
- https://de.dreametech.com/products/dreame-h11-core-nass-und-trockensauger → unvalidated
- https://de.dreametech.com/products/dreame-h12-pro-flexlite-nass-und-trockensauger → unvalidated
- https://de.dreametech.com/products/dreame-h12-pro-flexreach → unvalidated
- https://de.dreametech.com/products/dreame-h13-pro → unvalidated
- https://de.dreametech.com/products/dreame-h14-ae-nass-und-trockensauger → unvalidated
- https://de.dreametech.com/products/dreame-h14-dual-nass-und-trockensauger → unvalidated
- https://de.dreametech.com/products/dreame-h15-mix-nass-und-trockensauger → unvalidated

### WD10T654CBH/LD

- Catalog rows: Товары!A12601:H12601
- Identity status: reconciled
- Original title(s): Стирально-сушильная машина WD10T654CBH/LD
- Brand/category: Samsung / Стиральные машины
- Alternate code: None
- Variants: {'region': 'LD'}
- Candidates: WD10T654CBH/LD → regional_model (title_raw, confidence 0.98, brand.samsung.model); WD10T654CBH/LD → seller_sku (seller_sku_raw, confidence 0.7, catalog_field)
- Planned queries: WD10T654CBH/LD
- High-confidence identity query scope complete: False
- Dealer gate: official_search_not_complete_or_exact_found

| Official domain | Executed/replayed queries and evidence | Snapshots | Candidate outcomes |
|---|---|---:|---|
| samsung_kz | WD10T654CBH/LD: snapshot_replay, HTTP response=True, checked=False | 6 | {} |
| samsung_us | WD10T654CBH/LD: snapshot_replay, HTTP response=True, checked=False | 4 | {} |
| samsung_kr | WD10T654CBH/LD: not_executed, HTTP response=False, checked=False | 5 | {} |

No official product candidates were supported by the bounded saved evidence.

## HTTP and access scope

The eight new requests were four Samsung Jet queries (KZ/US) and four Kärcher marketing-model queries (KZ/global). No new Dreame request was executable through the saved declared routes. RLD35GD ambiguity blocks HTTP. Existing protected endpoints and HTTP host pauses were retained; browser evidence never pauses HTTP or other regional hosts. `challenge_suspected` does not prevent offline extraction from an existing snapshot; it does prevent repeating that HTTP endpoint in this run.

Detailed request receipts: [http_attempts.json](http_attempts.json). Before-network replay: [offline_results.json](offline_results.json). Final identities, complete raw rows, query metadata, all candidate verifications, snapshot references and scope hashes: [final_results.json](final_results.json). The final saved replay sends zero requests. Each new request and redirect consumes the aggregate 24, per-domain 10 and per-product 40 caps; at most three new target pages per domain and 40 seconds per domain/product. No domains or source registries were added.

## Validation and protected files

Tests: 255, passed: True. [tests.txt](tests.txt) contains the complete unittest result. It covers original-row/read-only loading, ambiguity, typed brand rules, parentheses priority, significant punctuation/region/service index, WB exclusion, structured name/body boundary, variant and model qualifier conflicts, checkpoint scope versions, offline replay, HTTP preconditions/redirect cap, method-scoped protection and immutable registries.

197 pre-existing protected files are byte-identical. The sole authorized existing-file change is `product_tool/identity.py` (backward-compatible optional fields and opt-in 7.1 verification). All Stage 2–7 report/snapshot files, source/dealer/domain registries, browser manual_review_only policy, unresolved-label/Accesstyle evidence, Sulpak allowlist, Mechta exclusion, workbook and user edits in jobs.py/storage.py/worker.py are unchanged.

[Before hashes](protected_hashes_before.json) · [Before/after hashes](protected_hashes_after.json).

## Recommended next stage — not implemented

Resolve the two-title RLD35GD identity with the catalog owner, then harden HTTP search-result completeness for the already verified official domains: distinguish real result/explicit-empty responses from search shells and review the reranked pending official URLs under a separately approved bounded run. Keep dealers closed until the revised complete official search warrants fallback. Do not resume browser strategy work or expand dealer scope.
