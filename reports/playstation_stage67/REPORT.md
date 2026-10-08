# Stage 67 — PlayStation exact discovery + CFI/SKU resolution

Stage acceptance: **PASS**. Verdict: **PlayStation adapter production-ready for controlled use**.
Same frozen ten inputs, SHA-256 `c2cac5f22132a2061c2ad114b1fa6030188f1ad26ddfc665734d0a75014d1422`; Stage 66 evidence was not rewritten.
Confirmed technical specs: **34 → 128**. Ready cards: **0 → 4/10** (three retail variants and one exact CFI hardware card). The six others remain not_ready because exact photos are missing, while their confirmed hardware facts remain available. Minimum three technical specs and exact photo requirement are preserved; manual is optional.

## Discovery and reproducibility

Before: family/support pages found, two selected photos and no ready cards; exact retail discovery and multi-row Slim routing were incomplete.
After: regional official → declared official sitemap → Direct homepage/catalog → Support/manual → other official regions → external search → dealer fallback. The official sitemap index is parsed with the existing sitemap parser. Public links from the Direct HTML sitemap are ranked by model and variant. The homepage publishes its search route, which publishes a GET catalog endpoint. SKU/name queries return candidate PDP links; own PDP SKU, product model and selected variant are validated before any facts are accepted. The runtime has no manually seeded SKU-to-URL map. Tests discover an invented SKU through a fake declared catalog, with external search forbidden by the fixture.

Live network evidence is in live_final.json and playstation_fetch.json; the final code is exercised in replay_acceptance.json against the same observed HTML/API/PDF responses, plus a subsequently discovered US Quick Start. Captures are keyed by observed final URL hashes, not by a SKU registry. Endpoint-declaration evidence is retained in observed/ and explore_http.json. Full trace retains queries, providers, URLs, source type, accepted/rejected reason and identity relation. Trace distinguishes candidate catalog links from accepted own PDPs. Query variants retain exact/normalized CFI, retail identifier, supplied model/variant name and family/name forms; bounded external search does not execute every variant.

External search is advisory here: Bing returned no candidates; Google returned 429 and its persisted stop was respected. The separate DuckDuckGo diagnostic encountered a challenge and stopped. No external search success is claimed. Existing browser/search contracts are reused, with an opt-in PlayStation classifier and decoding of observed public search redirect URLs before tracking redaction. Dealer sources are retained as review evidence and do not manufacture exact configuration facts.

## CFI and SKU boundaries

Exact CFI, family, nearby revision, regional suffix and another drive variant are distinct diagnostic relations. Only exact linked hardware tables can provide revision-specific values. CFI-1216A and CFI-1216B are independent: 390×104×260 mm / 3.9 kg versus 390×92×260 mm / 3.4 kg.

The official combined Slim table has explicit with-disc/without-disc columns. Exact CFI links and cover validation bind A/B to the matching column. CFI-2016B: 358×80×216 mm, 2.6 kg, without disc; CFI-2015A: 358×96×216 mm, 3.2 kg, with disc. Shared CPU/GPU, memory and storage rows remain separate from dimensions/weight. US CFI-2015A uses its US manual, including the published 100–240 V rating, rather than the GB regional row. Missing or reversed headers and an unbound CFI reject drive-specific candidates. Source labels and the A=Disc/B=Digital binding basis are recorded explicitly.

1000050213-GB publishes CFI-ZCT2W, not CFI-ZCT1W; only its own published retail features/photos/kit/color are accepted. Portal White publishes CFI-Y1016 and own selected White SKU 1000041537-GB. PULSE Elite Product JSON-LD publishes CFI-ZWH2EC, while Direct SKU 1000047820-GB publishes CFI-ZWH2: those are not merged. Elite readiness covers hardware only and carries an explicit retail-configuration advisory. Fortnite SKU 1000049849-GB publishes its Digital / 825 GB / bundle configuration, plus a CFI-2100 family statement, but no exact CFI; dimensions, weight and revision-specific ports/power remain unconfirmed for it.

## Specs, photos, documents and descriptions

PDP feature sections, own Product JSON-LD, official hardware tables, public catalog payloads and verified manual specifications contribute facts with preserved raw text and source URLs. CPU/GPU, memory, storage, I/O, networking, HDMI, power, dimensions, weight, operating temperature, display and battery data are extracted when present. Console specs stop before the bundled controller's specification block. Haptic feedback/adaptive triggers on console pages are explicitly labelled as DualSense controller features. Model-stable features do not imply a hardware revision; hardware facts do not imply retail color, kit or packaging.

15 actual official image responses were decoded and measured; **13 are finally selected**: Black DualSense 3, Portal 4, exact Elite MPN 5, Fortnite 1. Two ambiguous FT-abbreviated bundle images remain candidates after the strict bundle-name guard. Base model renders, other colors, gameplay and generic packaging remain candidates. Own SKU gallery alone does not override explicit color/bundle contradictions; all three additional negative gallery controls failed before the guard and pass afterward. Context photos do not confirm included accessories. Hardware specs are preserved independently of photo readiness.

RU User Guide content/cover is verified for CFI-ZCT1W and CFI-Y1016; their English guides are also verified. Five English Quick Starts are verified for 1216A, 1216B, 2016B, 7021 and US 2015A. Five English Safety Guides supply scoped hardware specifications and are never labelled User Guide. Black ZCT2W and Elite EC guides are unverified rather than borrowed from adjacent codes. Status “Не проверена” does not claim an exhaustive proof of absence.

Descriptions use purpose plus admitted source facts, with source-scoped claim lists. Support setup/reset/repair/firmware/warranty instructions do not become descriptions. Color and kit are included only for verified retail variants.

## Ten unchanged inputs

| ID / input | Model identity | Exact CFI | Retail SKU | Specs before → after | Photos before → after | RU User Guide / Quick Start | Readiness before → after |
|---|---|---|---|---|---|---|---|
| 1: CFI-1216A | ps5 confirmed | CFI-1216A | не подтверждён | 9 → 16 | 0 → 0 | Не проверена / Проверена | not_ready → not_ready (hardware_only) |
| 2: CFI-1216B | ps5 confirmed | CFI-1216B | не подтверждён | 9 → 16 | 0 → 0 | Не проверена / Проверена | not_ready → not_ready (hardware_only) |
| 3: CFI-2016B | ps5 confirmed | CFI-2016B | не подтверждён | 0 → 17 | 0 → 0 | Не проверена / Проверена | not_ready → not_ready (hardware_only) |
| 4: CFI-7021 | pro confirmed | CFI-7021 | не подтверждён | 9 → 21 | 0 → 0 | Не проверена / Проверена | not_ready → not_ready (hardware_only) |
| 5: CFI-ZCT1W | dualsense confirmed | CFI-ZCT1W | не подтверждён | 4 → 7 | 0 → 0 | Проверена / Не проверена | not_ready → not_ready (hardware_only) |
| 6: 1000050213-GB | dualsense confirmed | CFI-ZCT2W | 1000050213-GB | 1 → 3 | 2 → 3 | Не проверена / Не проверена | not_ready → export_ready (retail_variant) |
| 7: CFI-Y1016 | portal confirmed | CFI-Y1016 | 1000041537-GB | 2 → 13 | 0 → 4 | Проверена / Не проверена | not_ready → export_ready (retail_variant) |
| 8: CFI-ZWH2EC | elite confirmed | CFI-ZWH2EC | не подтверждён | 0 → 9 | 0 → 5 | Не проверена / Не проверена | not_ready → export_ready (hardware_only) |
| 9: CFI-2015A | ps5 confirmed | CFI-2015A | не подтверждён | 0 → 17 | 0 → 0 | Не проверена / Проверена | not_ready → not_ready (hardware_only) |
| 10: 1000049849-GB | ps5 confirmed | не опубликован | 1000049849-GB | 0 → 9 | 0 → 1 | Не проверена / Не проверена | not_ready → export_ready (retail_variant) |

## Confirmed scope inventory

The inventory below records all confirmed facts, including retail fields excluded from the technical-spec readiness count. Hardware provenance is shown as hardware scope even where the value could be stable across models; no cross-CFI stability is inferred.

### CFI-1216A

- model: adaptive_triggers_контроллер_dualsense = true bool; haptic_feedback_контроллер_dualsense = true bool
- hardware: product_dimensions__depth = 260 mm; product_dimensions__height = 104 mm; product_dimensions__width = 390 mm; product_weight = 3.9 kg; видеовыход = hdmi™ out port*3 ; графический_процессор = 10 tflops, amd radeon™ rdna-based graphics engine ; максимальная_потребляемая_мощность = 350 w ; объем_накопителя = 825 gb custom ssd*1 ; оперативная_память = gddr6 16 gb ; питание = 220—240 v 1.65 a 50/60 hz ; процессор = x86-64-amd ryzen™ “zen2”, 8 cores/16 threads ; рабочая_температура = 5 °c to 35 °c ; разъемы = usb type-a port (hi-speed usb) usb type-a port (superspeed usb 10gbps) ×2 usb type-c® port (superspeed usb 10gbps) expansion connector (key m) ; сетевые_интерфейсы = ethernet (10base-t, 100base-tx, 1000base-t) ieee 802.11 a/b/g/n/ac/ax bluetooth® 5.1 
- retail: не подтверждено
### CFI-1216B

- model: adaptive_triggers_контроллер_dualsense = true bool; haptic_feedback_контроллер_dualsense = true bool
- hardware: product_dimensions__depth = 260 mm; product_dimensions__height = 92 mm; product_dimensions__width = 390 mm; product_weight = 3.4 kg; видеовыход = hdmi™ out port*3 ; графический_процессор = 10 tflops, amd radeon™ rdna-based graphics engine ; максимальная_потребляемая_мощность = 340 w ; объем_накопителя = 825 gb custom ssd*1 ; оперативная_память = gddr6 16 gb ; питание = 220–240 v 1.60 a 50/60 hz ; процессор = x86-64-amd ryzen™ “zen2”, 8 cores/16 threads ; рабочая_температура = 5 °c to 35 °c ; разъемы = usb type-a port (hi-speed usb) usb type-a port (superspeed usb 10gbps) ×2 usb type-c® port (superspeed usb 10gbps) expansion connector (key m) ; сетевые_интерфейсы = ethernet (10base-t, 100base-tx, 1000base-t) ieee 802.11 a/b/g/n/ac/ax bluetooth® 5.1 
- retail: не подтверждено
### CFI-2016B

- model: adaptive_triggers_контроллер_dualsense = true bool; haptic_feedback_контроллер_dualsense = true bool
- hardware: product_dimensions__depth = 216 mm; product_dimensions__height = 80 mm; product_dimensions__width = 358 mm; product_weight = 2.6 kg; видеовыход = hdmi™ out port*3 ; графический_процессор = 10 tflops, amd radeon™ rdna-based graphics engine ; максимальная_потребляемая_мощность = 350 w ; объем_накопителя = 1 tb custom ssd*1 ; оперативная_память = gddr6 16 gb ; оптический_привод = без установленного привода ; питание = 220–240 v 1.65 a 50/60 hz ; процессор = x86-64-amd ryzen™ “zen2”, 8 cores/16 threads ; рабочая_температура = 5 °c to 35 °c ; разъемы = usb type-a port (superspeed usb 10gbps) ×2 usb type-c® port (hi-speed usb) usb type-c® port (superspeed usb 10gbps) expansion connector (key m) disc drive port ; сетевые_интерфейсы = ethernet (10base-t, 100base-tx, 1000base-t) ieee 802.11 a/b/g/n/ac/ax bluetooth® 5.1 
- retail: не подтверждено
### CFI-7021

- model: adaptive_triggers_контроллер_dualsense = true bool; haptic_feedback_контроллер_dualsense = true bool; tempest_3d_audiotech = true bool; максимальная_частота_кадров = до 120 fps ; поддержка_4k = true bool; поддержка_hdr = true bool; трассировка_лучей = true bool
- hardware: product_dimensions__depth = 216 mm; product_dimensions__height = 89 mm; product_dimensions__width = 388 mm; product_weight = 3.1 kg; видеовыход = hdmi™ out port*3 ; графический_процессор = 16.7 tflops, amd radeon™ rdna-based graphics engine ; максимальная_потребляемая_мощность = 390 w ; объем_накопителя = 2 tb custom ssd*1 *2 ; оперативная_память = gddr6 16 gb ddr5 2 gb ; питание = 220–240 v 1.9 a 50/60 hz ; процессор = x86-64-amd ryzen™ “zen2”, 8 cores/16 threads ; рабочая_температура = 5 °c to 35 °c ; разъемы = usb type-a port (superspeed usb 10gbps) ×2 usb type-c® port (hi-speed usb) usb type-c® port (superspeed usb 10gbps) m.2 ssd expansion connector (key m) disc drive port ; сетевые_интерфейсы = ethernet (10base-t, 100base-tx, 1000base-t) ieee 802.11 a/b/g/n/ac/ax/be bluetooth® 5.1 
- retail: не подтверждено
### CFI-ZCT1W

- model: adaptive_triggers = true bool; haptic_feedback = true bool
- hardware: product_weight = 0.28 kg; емкость_аккумулятора = 1 560 mah ; питание = 5 v 1 500 ma ; рабочая_температура = 5 °c to 35 °c ; тип_аккумулятора = built-in lithium-ion battery 
- retail: не подтверждено
### 1000050213-GB

- model: adaptive_triggers = true bool; haptic_feedback = true bool; микрофон = встроенный 
- hardware: не подтверждено
- retail: color = черный (midnight black) ; комплектация = dualsense® wireless controller; user manual 
### CFI-Y1016

- model: adaptive_triggers = true bool; haptic_feedback = true bool
- hardware: product_weight = 0.529 kg; время_зарядки = approx. 2 hours 30 minutes* ; динамики = built-in stereo speakers ; емкость_аккумулятора = 4 370 mah ; напряжение_аккумулятора = 3.87 v ; питание = 5 v 3 a ; рабочая_температура = 5 °c to 35 °c ; разъемы = usb port headset jack ; сетевые_интерфейсы = ieee 802.11 a/b/g/n/ac playstation linktm (2.4 ghz) ; тип_аккумулятора = built-in lithium-ion battery ; экран = 8-inch full hd lcd touchscreen 
- retail: color = белый ; комплектация = playstation portal™ remote player; usb cable; user manual 
### CFI-ZWH2EC

- model: playstation_link = true bool; время_работы_аккумулятора = до 30 ч ; микрофон = встроенный ; тип_излучателей = планарные магнитные ; шумоподавление_микрофона = с использованием ии 
- hardware: product_dimensions__depth = 214 mm; product_dimensions__height = 251 mm; product_dimensions__width = 147 mm; product_weight = 0.4 kg
- retail: не подтверждено
### CFI-2015A

- model: adaptive_triggers_контроллер_dualsense = true bool; haptic_feedback_контроллер_dualsense = true bool
- hardware: product_dimensions__depth = 216 mm; product_dimensions__height = 96 mm; product_dimensions__width = 358 mm; product_weight = 3.2 kg; видеовыход = hdmi™ out port*4 ; графический_процессор = 10 tflops, amd radeon™ rdna-based graphics engine ; максимальная_потребляемая_мощность = 350 w ; объем_накопителя = 1 tb custom ssd*1 *2 ; оперативная_память = gddr6 16 gb ; оптический_привод = ultra hd blu-ray ; питание = 100–240 v 3.55 –1.5 a 50/60 hz ; процессор = x86-64-amd ryzen™ “zen2”, 8 cores/16 threads ; рабочая_температура = 5 °c to 35 °c (41 °f to 95 °f) ; разъемы = usb type-a port (superspeed usb 10gbps) ×2 usb type-c® port (hi-speed usb) usb type-c® port (superspeed usb 10gbps) expansion connector (key m) disc drive port ; сетевые_интерфейсы = ethernet (10base-t, 100base-tx, 1000base-t) ieee 802.11 a/b/g/n/ac/ax bluetooth® 5.1 
- retail: не подтверждено
### 1000049849-GB

- model: adaptive_triggers_контроллер_dualsense = true bool; haptic_feedback_контроллер_dualsense = true bool; tempest_3d_audiotech = true bool; максимальная_частота_кадров = до 120 fps ; поддержка_4k = true bool; поддержка_hdr = true bool; трассировка_лучей = true bool
- hardware: не подтверждено
- retail: комплектация = playstation®5 digital edition console*; dualsense® wireless controller; fortnite flowering chaos bundle voucher**; florin outfit (with lego® style); blossom backpack back bling; floral finisher pickaxe; blue blossoms wrap; petal's edge guitar; blue bloom mic; petal steppers kicks; 1,000 v-bucks; 825 gb ssd (solid-state drive); 2 plastic stand feet to place the console horizontally; hdmi® cable; ac power cord; usb cable; user manual; astro's playroom (pre-installed game)*** ; объем_накопителя = 825 gb ; оптический_привод = digital 

## Validation and controlled-use boundary

All ten UI pages returned HTTP 200. Native exporter output is checked for formula errors, scope labels, exact SKU–CFI relations, candidate photos and separate document roles/languages. Read-only Artifact Tool import/render inspects the existing native workbook; it does not reauthor it. Its Node process returned native Windows status -1073740791 after writing the five renders and inspection; this is recorded as a tool-runtime limitation, not a successful process exit. All five PNGs are independently decoded and visually reviewed, and the native exporter/workbook validation passes separately. Headless local screenshots use actual captured image bytes and verified measurements; the gallery lightbox is checked. Newly discovered US Quick Start cover and hardware table are visually inspected. See qa_ui_excel.json, artifact_render_validation.json, document_render.json, photo_inspection.json and retained screenshots.

Zero conflicting resolved values and zero false confirmed retail facts were observed in this ten-row acceptance audit. Each confirmed retail claim is asserted against its own accepted PDP; dimensions/weight/power/ports require hardware provenance; each accepted hardware source names the selected exact CFI. This is evidence for the frozen acceptance set, not a universal guarantee for every future Sony page.

Full regression: ['Ran 1584 tests in 867.710s', 'OK']; source tree unchanged: True. The previous regression was interrupted before the three gallery controls were added; only regression_release.json represents the final run. Historical Stage 66 reports/pins remain untouched; current authorized shared edits are recorded in migration_record.json.

Controlled use means exporting verified retail variants with their published scope, or exact hardware cards with an explicit missing-retail advisory; unresolved cards retain review gates. Outstanding review: six exact-photo gaps, unverified manuals where noted, no retail SKU/kit/color for hardware-only cards, and no exact Fortnite CFI. General brand approval does not turn those gaps into confirmed facts. SKU–CFI diagnostics distinguish published candidate links from links accepted for the requested identity; disc drives, stands, charging stations and PULSE Explore compatibility mentions do not establish PS5 console identity.
