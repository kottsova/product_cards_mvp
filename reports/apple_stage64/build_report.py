from pathlib import Path
import json
r=Path('reports/apple_stage64');a=json.loads((r/'before_after.json').read_text(encoding='utf-8'));reg=json.loads((r/'regression_release.json').read_text(encoding='utf-8')) if (r/'regression_release.json').exists() else {};passed=reg.get('exit_code')==0 and reg.get('source_tree_unchanged') and any('Ran 1519 tests' in line for line in reg.get('result',[]));status='audit PASS' if passed else 'audit complete; regression pending'
text=f"""# Stage 64 — Apple baseline audit и перенос общего pipeline

Дата: 2026-10-07. Исходный commit: `c2dec8d1d31492b6e185bf1bafcb5be5532daad3`.

**Stage 64: {status}. Verdict: `Apple adapter not ready`.** Аудит и небольшой консервативный adapter завершены. Это не production PASS Apple. Ни маркетинговое имя, ни A-number, ни наличие commercial SKU в странице не превращают все family options в конфигурационные факты.

## 1. Baseline Apple result

Контроль: `FW123LL/A`, Apple Certified Refurbished MacBook Air 13-inch, M4, 2025, Midnight, 16GB unified memory, 256GB SSD, 10-core CPU / 8-core GPU. Refurbished condition сохранён отдельно; F-order number не заменён M-retail number. Hardware A-number точного baseline официально не связан и не объявлен подтверждённым.

Сначала обычный `run_once()` на исходном Stage63, без Apple-specific hardcode: job `error`, readiness `not_ready`, 0 facts / 0 photos / 0 documents / 0 conflicts. Официального Apple dispatch не было; общий DNS путь потребовал подтверждённый dealer URL. Discovery trace в этой старой unsupported-brand ветке отсутствует — сохранены source pages и job events. [baseline.json](baseline.json).

После общего переноса: тот же `run_once()`, job `done`, 13 подтверждённых полей, {a['baseline_after']['photos_selected']} selected gallery assets, 0 conflicts. `exact_order_model / exact_part_number / exact_order_variant`. Прототипный configuration gate даёт `export_ready`; RU manual `Не проверена`, advisory. Это ограниченная проверка конфигурации/specs/photo, а не доказательство завершённой production-карточки.

[Официальная order PDP](https://www.apple.com/shop/product/fw123ll/a) содержит точный Product Offer SKU, singleton Memory/Storage и ImageGallery. [Tech Specs семьи](https://support.apple.com/en-us/122209) перечисляет возможные конфигурации. Исходные ответы, SHA-256, title, raw sections и findings: [official_sources.json](official_sources.json), [source_structure.json](source_structure.json).

## 2. Official Apple source structure

Исследованы 20 official URLs и фактические order pages frozen dataset. Все исследовательские источники доступны HTTP200. [more_sources.json](more_sources.json).

- Store `/shop/product/<part-number>`: redirect к semantic PDP; JSON-LD Product, Offer.sku, condition, ImageGallery. Exact SKU проверяется в payload, а не только в URL. Refurbished PDP может содержать как точные поля, так и переиспользованные семейные блоки.
- Store `/shop/buy-iphone/...`: AggregateOffer + `window.PRODUCT_SELECTION_BOOTSTRAP.productSelectionData`. Records связывают `partNumber`, `familyType`, `dimensionScreensize`, `dimensionColor`, `imageKey`; `displayValues` и `imageDictionary` хранят labels и renders. На исследованном iPhone16 интерфейсе storage не представлен отдельным полем каждого record. UI dimension text недостаточен для заранее построенного универсального resolver.
- `support.apple.com/<locale>/<numeric-id>`: server-rendered Tech Specs, h2/h3 sections, model/generation title. Разделы Memory/Capacity/Finish часто являются options. [iPad A16](https://support.apple.com/en-us/122240), [MacBook Pro M4](https://support.apple.com/en-us/121552), [Watch Series10](https://support.apple.com/en-us/121202), [AirPods4 ANC](https://support.apple.com/en-us/121204).
- `apple.com/.../specs/`: model-family pages; US и UK могут различаться cellular/SIM/regional условиями. Compare — comparison/discovery source, не exact order PDP.
- Sitemap и robots реально получены; sitemap хранит indexed family/product URLs. Он не является таблицей part→configuration.
- `/guide/.../welcome/...`: HTML User Guide / Getting Started, связанные с family/OS; support article, Tech Specs, repair, safety и warranty не заменяют User Guide.
- Embedded public bootstrap исследован. API references сохранены в source_structure.json. Отдельный XHR network trace не снимался; unobserved API endpoints не объявлены verified. Purchase/cart/payment endpoints не вызывались.

## 3. Identity rules

Раздельно сохраняются модель/поколение/размер корпуса, commercial configuration и variant/color. Для точной order page требуется HTTPS official host, один Product и один distinct commercial SKU в Offer, совпадающий с исходным полным артикулом. Полный SKU с другим suffix не приравнивается исходному. Prefix F/M и неизвестные suffix не отбрасываются.

`exact_part_number` означает доказанную связь order SKU со страницей. Это ещё не `configuration_complete`: каждое поле проверяется отдельно. Family options, configurable/available/optional values остаются evidence candidates. Conflicting dimensions не выбираются автоматически. Russian canonical labels для допущенных CPU/RAM/storage/dimensions/runtime сохраняются вместе с исходными section/label/value в evidence.

Photo gate независим от storage. iPhone record с exact requested partNumber + model/color imageKey + соответствующим imageDictionary URL подтверждает модель/цвет изображения, даже когда storage unresolved. Gallery чужого цвета не подтверждается; synthetic mismatch покрыт тестом. Визуальная проверка iPad выявила, что Silver filename используется и для box/multicolor montage. Классификация учитывает matched image alt: packaging и multiple exterior colors теперь candidates, не selected product gallery. Это покрыто отдельным тестом на реальной PDP. Другой commercial SKU и A-number не наследуют фото или specs exact order page.

[Identify your iPhone model](https://support.apple.com/en-us/108044) реально перечисляет для iPhone16 несколько capacities/colors и regional A-models. A3081 относится к US/Puerto Rico model family; это не таблица order SKU→storage/color. [hardware_relation_observed.json](hardware_relation_observed.json).

## 4. Model vs configuration findings

1. MacBook baseline FW123LL/A даёт 16GB/256GB/8-core GPU; FC6U4LL/A той же семьи Air M4 — другой order SKU, 16GB/512GB/10-core GPU и Sky Blue. Один model name не определяет GPU/RAM/SSD/color.
2. iPad FD3Y4LL/A title и Offer относятся к 128GB Silver, но Tech Specs блока этой PDP перечисляет 128/256/512GB. Все три сохранены candidates; capacity facts не допущены. FD4A4CL/A также сохраняет regional part и Blue отдельно.
3. Watch FWWU3LW/A относится к 46mm GPS Rose Gold + конкретному band bundle, но её Tech Specs содержит 42mm и 46mm. Width/Height разных корпусов дали unresolved conflicts; они не стали confirmed. Общая глубина и Neural Engine допускаются отдельно.
4. AirPods4 MXP93LL/A official route теперь ведёт к AirPods5. Исходный SKU не найден в order record новой страницы. Новое поколение не подменило исходное; ни specs, ни фото AirPods5 не подтверждены для AirPods4.

Это доказательства необходимости scoped field resolution, а не просто normalizer после текста.

## 5. Battery/runtime rules

Раздельные поля: video playback, streamed video, audio playback, wireless web. Baseline MacBook использует **video streaming**, поэтому это отдельное поле от обычного video playback. Official watt-hours сохраняются без вывода сторонних mAh. Published “up to” сохраняется как исходный maximum-runtime statement, не гарантированное время эксплуатации.

Для iPad общий statement “web on Wi-Fi or video” сохранён verbatim в raw evidence. Текущий canonical mapping допускает video statement, но отдельный web field ещё не построен; это системный mapping gap. Watch normal-use / Low Power / sleep / charge metrics остаются отдельными raw candidates и не свёрнуты в единый battery number. Полный mode-aware mapping входит в оставшиеся production blockers.

## 6. Manuals

Реально получены русские iPhone, MacBook Air, iPad, Watch, AirPods guide landing pages. Их titles/language/status сохранены в [manual_review.json](manual_review.json). Это подтверждает существование family/OS guide, но не content coverage конкретного поколения/артикула. У всех 11 audit rows статус `Не проверена`; отсутствие RU-инструкции не заявлено. “Проверена, не найдена” не использовано без полноценной проверки.

Manual является advisory в Apple configuration gate. Typed guide discovery/verification ещё не подключён к production Apple documents; support/help content не импортирован в description. Описания оставлены пустыми, чтобы не включить setup/iCloud/reset/repair/troubleshooting.

## 7. Frozen dataset

10 новых SKU, baseline отдельно. Три retail iPhone16 color SKU, два refurbished MacBook, один iPad, один Watch, один AirPods и два сложных regional/refurbished cases. Часть выборки refurbished — это явно сохранённое условие, а не подмена retail. Stock availability не используется как identity proof. Dataset зафиксирован до первого worker run и не менялся.

`dataset_frozen.json` SHA-256: `{a['dataset_sha256']}`.

## 8. First-pass и adapter results

Первый прогон — без Apple adapter: все 10 `error / not_ready`, 0 facts. Это системное отсутствие dispatch, не десять доказанных source gaps. [first_pass.json](first_pass.json).

После небольшого adapter — обычный worker, без injected model URLs и без per-SKU hardcode. [final_acceptance.json](final_acceptance.json), [before_after.json](before_after.json).

| SKU | Модель/вариант | Confirmed specs | Selected photos | Job | Configuration gate |
|---|---|---:|---:|---|---|
"""
for row in a['models']:
 text+=f"| `{row['article']}` | {row['identity'].get('model','unproven')} / {row['identity'].get('variant','unproven')} | {row['readiness']['confirmed_specs']} | {row['photos_selected']} | {row['after_job']} | {row['readiness']['verdict']} |\n"
text+=f"""
Итого: {a['counts']['raw_facts']} raw facts, {a['counts']['confirmed_specs']} confirmed specs, {a['counts']['photos_selected']} selected images; 2 rows проходят ограниченный gate, 8 not_ready. Baseline ещё 13 facts / {a['baseline_after']['photos_selected']} images.

Exact order identity имеется у 6 dataset rows; три iPhone имеют partial selection model/color relation; AirPods остаётся unproven. Dealers проверены как отдельный fallback: подтверждённого exact dealer URL/configuration не получено. Dealer facts не смешаны с official.

Shared external Google реально вызван для 3 iPhone и AirPods: во всех четырёх `no_candidates`. Используется существующий LGBrowserSearch; новый Apple Google engine не создан. Query/provider/URL/region/source_type/admission reason/identity сохраняются в discovery_trace. Search results сами по себе не подтверждают товар. Official family/support discovery пока неполно встроен в production route и является blocker.

## 9. Identity edge cases / false confirmations

14 offline tests + 6 ручных reviews: [identity_review.json](identity_review.json). Другой commercial storage SKU, другой region suffix, A-model, family Tech Specs, разные colors, conflicting exact-gallery color, multi-SKU Offer и fake official host не повышены до исходной конфигурации. Synthetic cases явно отмечены. Реальные iPhone black/white имеют разные confirmed photo URLs и ноль допущенных configuration facts.

Storage facts существуют только у двух exact MacBook dataset rows; iPad/iPhone family capacities не стали exact. Watch height/width conflicts не имеют full_sku_confirmed. Проверки negative admission и реальных storage outputs прошли.

## 10. UI / Excel и configuration-resolution layer

11 production UI pages HTTP200. Apple audit section показывает model/configuration/variant, candidates, manual status. Source header больше не называет найденную Apple страницу отсутствующим источником. Photo candidates доступны в Apple UI; отдельный экспорт их URLs/reasons в Excel ещё не реализован и остаётся системным presentation gap. Native Excel exporter создаёт “Готовность Apple” и “Варианты-кандидаты Apple”; {json.loads((r/'qa_ui_excel.json').read_text(encoding='utf-8'))['sheets']['Варианты-кандидаты Apple']['rows']} candidate rows включая header; формульных ошибок нет. Существующие вкладки других брендов сохранены. [qa_ui_excel.json](qa_ui_excel.json).

Spreadsheets artifact-tool использован только для read-only import/inspect/render native export. Проверены [excel_readiness.png](excel_readiness.png), [excel_identity.png](excel_identity.png), [excel_candidates.png](excel_candidates.png). 12 UI renders и 37 исходных gallery assets проверены. После alt-aware фильтра selected product gallery содержит 26 assets включая baseline; остальные 11 — packaging/family/uncertain candidates. Gallery bytes имеют собственные SHA/dimensions; offline renders используют сохранённые actual images, без подмены цвета/ракурса.

**Configuration-resolution layer нужен.** Достаточно небольшого общего слоя field scope + joins между order records/title dimensions и family specs. Он должен разрешать storage/RAM/GPU, screen/body size, Wi-Fi/Cellular, watch case/band, region и condition. Сохранение, jobs, normalization, evidence, общий search, UI и Excel переиспользуются. Отдельный Apple framework заранее не построен.

## 11. Regression

14 Apple targeted tests — OK. Final full regression: {('; '.join(reg.get('result',[]))) if passed else 'pending'}. Source tree unchanged: {reg.get('source_tree_unchanged','pending')}. [regression_release.json](regression_release.json). Перед commit выполняется git diff --check и проверка response hashes в Git index.

## 12. Verdict и concrete blockers

**`Apple adapter not ready`.** Остаются:

- scoped commercial configuration resolution, включая carrier/storage selector и watch 42/46/body/band;
- complete model-level Tech Specs discovery/admission и category-aware readiness;
- полный Russian canonical mapping: display/cameras/wireless/features, separate iPad web/video, watch battery modes;
- typed manual content verification и безопасное product description extraction;
- согласование общего batch readiness с Apple audit gate; сейчас common generic gate ещё ожидает старую official/full-SKU/document схему;
- exact dealer URL/configuration для unresolved rows; AirPods4 historical source recovery вместо поколения5.

Это системные implementation gaps. Реальные source gaps: отсутствует exact order record части коммерческих SKU в текущем storefront, old AirPods route изменён, guide coverage конкретных поколений не проверена. Нельзя объявить Apple production-ready по двум MacBook rows.

## 13. GitHub / reproduction

После audit PASS и полного regression: commit `Stage 64`, push origin/main, HEAD==origin/main, clean working tree. Actual hash сообщается в финальном ответе без self-referential записи в этот отчёт.

`run_baseline.py` / `run_first_pass.py` — historical unchanged Stage63 runs; fresh replay требует старого source checkout. `run_final_acceptance.py` — current ordinary worker для того же frozen dataset, fresh DB required. `PYTHONPATH=.`; Browser runtime использует `.venv/playwright-browsers`. HTML/capture manifests и frozen dataset сохраняются byte-exact через .gitattributes; DB/XLSX/logs/node_modules не публикуются. Source captures/metadata и raw sections позволяют независимую перепроверку без воспроизведения сетевой доступности.
"""
(r/'report.md').write_text(text,encoding='utf-8')
