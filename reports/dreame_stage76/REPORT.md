# Stage 76 — Dreame model-first audit

Дата: 2026-10-11 (Asia/Tbilisi). Исходный commit: `74df7eabc75865774d0b09ffc2ca24b2b0d4d175`.

**Stage 76 audit/transfer: PASS. Полный regression: 1787 tests, OK; исходники во время прогона неизменны.**

**Вердикт адаптера: `Dreame adapter not ready`.** В обычном worker подтверждено **0/10 live official product sources, 0 характеристик, 0 фото, 0 ready**. Web-исследование, отдельный PDF download и offline contracts не подставлялись в карточки.

Stage 76 оценивает audit и перенос общего pipeline. Здесь не введён новый минимальный процент live success и не снижены production readiness thresholds. Полный regression и итоговая оценка критериев записаны в `regression_release.json` и `release_verification.json`.

## 1. Baseline до изменений

Обычный `run_once()` выполнен на исходном commit для `H14 Pro`, название `Dreame H14 Pro [region=Global]`, категория «Вертикальные моющие пылесосы». Supplier SKU не предоставлен; bundle отсутствует. Вход прошёл штатный Excel importer.

Результат: `job=error`, официального источника нет, model identity не подтверждена, specs/photos/documents = 0. До изменения dispatch Dreame попадал в общий dealer-only маршрут; для DNS не было проверенного URL. Именно это объясняет baseline error. Официальный поиск этим worker не выполнялся, поэтому его discovery trace пуст; события job сохранены. Варианты `H14 PRO`, `Dreame H14 Pro`, `H14 Pro` зафиксированы для последующего анализа, а не выданы за выполненные поисковые запросы baseline.

Отдельный диагностический запрос official homepage получил реальный HTTP 429. Это второй, внешний блокер, отличный от отсутствовавшего Dreame dispatch. Exact H14 Pro PDP обнаружен позднее в опубликованной навигации при web-исследовании: [H14 Pro](https://global.dreametech.com/products/h14-pro). Это **не** результат baseline discovery и **не** seed адаптера.

Полный вход, job, события, sources, readiness, diagnostic и результат попытки attended browser: `baseline/results.json`. CUA не дошёл до навигации из-за ошибки запуска sandbox/kernel; attended success не заявляется.

## 2. Official structure и происхождение данных

| Канал | Наблюдение | Что он доказывает |
|---|---|---|
| Обычный HTTP Global/US/DE | 429; сохранённые rate-limit stops | Реальную проблему native transport |
| Обычный HTTP `www.dreame.tech` | 200, сохранённый Nuxt HTML | Китайский официальный frontend; не связь китайских product IDs с глобальными моделями |
| Web research Global | Published catalog → exact product links, страницы specifications и manuals | Навигацию и публичные semantics; не native worker success и не сырой Shopify DOM |
| Исторический DE census | Product JSON-LD: name/sku/gtin13/image; таблица specs не получена | Только ранее наблюдавшийся identity/gallery contract; не текущую live extraction coverage |
| Отдельный официальный CDN PDF | H12 Dual RU, HTTP 200 | Реальный User Guide и language/type/model relation вне worker |

Global использует отдельные published `/products/…` маршруты, включая коммерчески отличающиеся slug. Например, X50 Ultra Complete имеет опубликованную страницу [X50 Ultra Complete](https://global.dreametech.com/products/dreame-x50-ultra-complete). Адаптер берёт href из catalog/sitemap, а не генерирует PDP URL из model name. Product/title подтверждает identity после загрузки кандидата; URL служит только для ранжирования.

Support route: [FAQs & Manuals](https://global.dreametech.com/pages/user-manuals-and-faqs) → model-specific HTML → опубликованный CDN PDF. Это исправило исходное предположение «индекс сразу содержит PDF». На Global опубликованы отдельно [H14 Pro manual page](https://global.dreametech.com/pages/h14-pro-user-manual) и [H12 Dual manual page](https://global.dreametech.com/pages/h12-dual-user-manual).

Production extraction binding читает Product JSON-LD additionalProperty, main/spec table/list/dl blocks, published model gallery и явные component headings. **Текущие Global SSR selectors, embedded product payload/XHR и полнота gallery на реальном native PDP остаются не квалифицированы из-за 429.** Наличие такого binding и успешные contracts не выданы за доказанное полное live extraction.

## 3. Model-first identity

Переиспользованы существующие worker, `xiaomi_pipeline` через параметр family, evidence store, normalization/resolution, readiness, photo verification, UI и exporter. Новые файлы — небольшой Dreame source/parser/presentation binding. Новый pipeline framework не создан.

Exact official model подтверждает model-level specs. Supplier part number, region, color, bundle, accessory pack и special edition из входного `[key=value]` блока сохраняются отдельно. Opaque article — supplier identifier, а не автоматически official SKU. Product JSON-LD name/model/sku/productID сохраняются как опубликованные поля; связь с supplier SKU не выдумывается.

Другой официальный регион допустим для модели. Региональная маркировка не блокирует готовность; candidate scope применяется только при явной published variation. Near models, другая generation, Pro/Max/FlexReach не объединяются. Ввод `X50 Ultra [bundle=Complete]` может связаться с явно напечатанным X50 Ultra Complete; это не доказывает состав аксессуаров. `H12 Dual` сохраняется как опубликованное model name, а не выводится из соседнего H12.

Добавлена adversarial защита: primary PDP h1/title имеет приоритет над Product JSON-LD рекомендации другой модели. Другой товар из recommendations не подтверждает входную модель.

## 4. Component/station rules

Факт сначала сохраняется как source section + raw label + raw value. Затем только по явному label/heading назначается компонент:

| Scope | Правило |
|---|---|
| Робот | Явный robot heading/label или категория робота для обычных device facts |
| База / станция | Явные station/dock/base/PowerDock markers |
| Устройство | Основное wet/dry или stick устройство |
| Ручной пылесос | Явный handheld component/mode |
| Упаковка | Packaging, не размеры/вес самого товара |
| Комплектация | Published package/accessory inventory остаётся candidate вне общих model specs |

Общая normalization сохраняет component section в canonical key. Weight/tank робота и станции не сталкиваются. Для robot PDP неоднозначные clean/dirty/detergent tank и dust bag без явной component relation остаются candidates; литры сами по себе не доказывают station. Packaging/bundle не становятся confirmed model facts.

Dimensions остаются исходной тройкой, если оси не напечатаны. Только явный `(W x D x H)` позволяет получить отдельные width/depth/height и mm. Например, на [L60 Ultra](https://global.dreametech.com/products/l60-ultra) отдельно опубликованы размеры и вес robot и base; две высоты robot относятся к положению сенсора. Из этих тройных значений без порядка осей W/H/D не выведены и в worker не внесены.

## 5. Tanks/runtime и raw → accepted → candidate

Примеры ниже проверены при **web research**, а не внесены в заблокированные live карточки.

| Модель | Raw fact | Правильное представление |
|---|---|---|
| [H14 Pro](https://global.dreametech.com/products/h14-pro) | Clean water 880 mL | Отдельный бак чистой воды устройства |
| H14 Pro | Used water: standing 650 mL; lie-flat 450 mL | Два значения грязного бака с operating position |
| H14 Pro | Maximum runtime 40 min | Заявленный максимум, без придуманного Eco/Turbo |
| [H12 Dual](https://global.dreametech.com/products/h12-dual) | Runtime 35 min wet/dry; 60 min handheld | Device и handheld runtime отдельно |
| H12 Dual | Working modes: Auto/Suction; Standard/Turbo | Сохраняется компонент каждой пары |
| [L60 Ultra](https://global.dreametech.com/products/l60-ultra) | Robot weight 4.01 kg; base weight 9.14 kg | Два component-scoped факта |

Contract fixtures проверяют blank continuation row с standing/lie-flat, runtime Eco/Turbo, wet/dry vs handheld, `Up to` и mm derivation. Исходная полная строка сохраняется до derived fields. Значение `Up to` остаётся заявленным максимумом; режимы не сворачиваются в одно «Время работы».

На production worker raw/accepted/rejected specs = 0, поскольку PDP не получен. Это отсутствие доступа, а не доказательство, что официальных specs нет. Полнота сложных реальных SSR/rowspan/colspan blocks ещё требует native capture; она не объявлена завершённой.

## 6. Frozen dataset

Зафиксирован **после baseline и до первого batch**, SHA-256:
`7872d84dabdda9b716cd594276273b5560832b2720709cb6610ed1ecbb521afd`.

10 различных моделей: 5 robots, 3 отдельных wet/dry, 1 stick, 1 Dual; X40 Master — сложный station case. Это audit inputs из published navigation, а не притворный supplier order. Реальные supplier SKU не предоставлены и не придуманы. `dataset.json` не содержит PDP URL seeds и после заморозки не менялся.

## 7. First-pass и финальный run

Таблица описывает worker, а колонка research PDP содержит только независимый published route. Во всех строках: identity unproven, specs/photos 0/0, manual `Не проверена`, job `needs_review`, readiness `not_ready`.

| ID | Модель / тип | Research PDP | First live | Final live | Главный gap |
|---|---|---|---:|---:|---|
| 1 | L60 Ultra / robot | [official](https://global.dreametech.com/products/l60-ultra) | 0 | 0 | 429/cooldown до catalog |
| 2 | L10s Pro Gen 2 / robot, EEA input | [official](https://global.dreametech.com/products/l10s-pro-gen-2) | 0 | 0 | 429/cooldown до catalog |
| 3 | D30 Ultra / robot | [official](https://global.dreametech.com/products/d30-ultra) | 0 | 0 | 429/cooldown до catalog |
| 4 | X50 Ultra / Complete input | [official](https://global.dreametech.com/products/dreame-x50-ultra-complete) | 0 | 0 | 429/cooldown до catalog |
| 5 | H14 Pro / wet-dry | [official](https://global.dreametech.com/products/h14-pro) | 0 | 0 | 429/cooldown до catalog |
| 6 | H13 Pro / wet-dry, RU input | [official](https://global.dreametech.com/products/h13-pro) | 0 | 0 | 429/cooldown до catalog |
| 7 | H15 Pro Heat / wet-dry | [official](https://global.dreametech.com/products/dreame-h15-pro-heat) | 0 | 0 | 429/cooldown до catalog |
| 8 | Z30 / stick | [official](https://global.dreametech.com/products/z30) | 0 | 0 | 429/cooldown до catalog |
| 9 | H12 Dual / Dual | [official](https://global.dreametech.com/products/h12-dual) | 0 | 0 | 429/cooldown до catalog |
| 10 | X40 Master / water-hookup station input | [official](https://global.dreametech.com/products/x40-master) | 0 | 0 | 429/cooldown до catalog |

Native order: normalized query → requested-region-ranked official catalog/sitemap → published candidate PDP → other official regions → support → existing external fallback → existing dealer stage. The recorded trace includes query/provider/URL/source type/decision/reason/model relation. No known product URL was supplied to `find_source()`.

Global 429: `2026-10-10T22:50:13Z`, expiry `23:50:13Z`, TTL 3600 seconds. US and DE have their own observed 429 entries. `scope=domain` means that exact host, not every subdomain of the company. Frozen batch attempts occurred within these temporary stops. Shared policy returns `[policy_host_stopped]` before network I/O; its 403-shaped response is **not a newly observed storefront HTTP 403**.

One adapter/session is reused across rows. Stop logs were copied with original timestamps, never erased/expired artificially. Actual worker successes were not reconstructed from research data. First-pass inherited a misleading `live_http` tag for a policy refusal; final trace labels these events `policy_refusal`. Their live_success flags remained false in both runs. Metadata alone is not counted as a live request.

The existing external browser helper also stops when its primary official host is paused (`lg_access_stop`), before Google navigation. This is a shared fallback coupling, not evidence of Google CAPTCHA/429. It was identified and preserved. DNS stage returned no trusted dealer URL; it did not guess one.

## 8. Edge cases, photos, manuals and UI/Excel

21 targeted contracts pass, including supplier SKU independence, other/absent region, near-generation rejection, robot/station canonical keys, handheld/runtime, clean/dirty tank position, explicit axes, package candidates, missing color relation, explicit other color, primary-vs-recommended product identity, exact RU guide and Safety exclusion. Most HTML cases are clearly labelled synthetic `Audit R1`; real H12 Dual PDF is the document fixture.

Model gallery can be confirmed without supplier-color evidence. Explicit other published color remains candidate. Gallery URLs enter normal byte verification (full image decoder, MIME, dimensions/size/hash); synthetic PNG tests validate that path. **Actual byte-verified worker gallery images = 0.** No fake image was placed in the production export.

Worker manual inventory for all 10 is `Не проверена` because official navigation was technically inaccessible. This is advisory, not a blocking readiness gap. Separate bounded research found manual detail pages for IDs 2/4/5/6/7/8/9/10. For L60/D30, no exact entry was found in the inspected index; this is not a global absence claim. Only H12 Dual PDF has been byte/type/language/model checked. The shared X50 Ultra/X50 Ultra Complete page proves shared guide coverage, not accessory contents.

Verified separate guide: [H12 Dual Russian User Guide](https://cdn.shopify.com/s/files/1/0302/5276/1220/files/W2221C.pdf?v=1757404110), 13 pages, 4,119,109 bytes, `application/pdf`, SHA-256 `88e3caba3ae154db8b9a601b3b0c1defddd4fca27447bb556a8238ed683ff3d4`. Cover and maintenance pages inspected. It includes operation/charging/maintenance sections, so it is not a Safety-only leaflet. Its Russian heading exposed and fixed a Dreame-specific false rejection. It was **not** injected into worker documents. H14 Pro's first published PDF exceeded the 15 MB bounded download budget; no large exhaustive search was performed.

All 10 actual cards return HTTP 200 through the local UI; source identity remains unconfirmed. Russian scope/input/manual labels are shown, no support/help text became a description. Component/raw audit is available in the native `Dreame компоненты` Excel sheet; it is empty for the blocked live rows. Populated component UI/export contracts are checked offline. Existing branded terms are preserved.

`Dreame_Stage76.xlsx` is the existing app exporter result, not an independently authored substitute. Readiness/configuration/robot sheets and four local UI screenshots were visually inspected. No XLSX error cells found. Artifact-tool produced three read-only render PNGs, then exited 1; that teardown limitation is recorded without claiming successful process completion. Actual production facts/gallery visual coverage remains unavailable.

## 9. Is a separate component-resolution layer needed?

**No separate framework is justified by the observed cases.** Existing section-scoped canonical keys, raw evidence, candidates and shared resolution suffice for the proven robot/station/device/handheld distinctions. The small source binding identifies explicit components; it does not solve ambiguous relations by guessing. This is a bounded architecture conclusion, not proof that every unseen Dreame SSR/bundle is already covered. A new layer should be considered only if native captures demonstrate relations the current representation cannot preserve.

## 10. Regression

Full command: `.venv\Scripts\python.exe -X utf8 reports/dreame_stage76/run_regression.py`.
Runner saves source hashes before/after, uses the existing whole-suite offline network guard, and records exit code/test count in `regression_release.json`. Prior reports/datasets were not rewritten. Stage 76 migration authorization was appended; its previous byte prefix is intact. Standalone targeted run: 21 Dreame contracts, plus 25 Xiaomi contracts passed in the preceding transfer check. Final full-suite result is authoritative.

`git diff --check` passed before final release assessment. No global readiness thresholds, access policy or external guard were weakened. Model readiness still requires sufficient official model facts and a verified selected model gallery; manual is optional.

## 11. Verdict and release gates

Production blockers:

1. Native official Global/US/DE product discovery unavailable under observed 429/cooldown; no successful attended session.
2. Existing external helper couples official-host stop to external search, so fallback did not navigate.
3. No native exact PDP specs/gallery captured for the 10; current SSR/embedded/XHR extraction completeness unqualified.
4. No actual worker photo bytes verified; worker manuals technically unvisited. Manual alone is not a readiness blocker.

`Dreame adapter not ready` is required. No unsupported supplier SKU/color/bundle/component configuration facts were confirmed. The audit result is recorded separately from production readiness; it is not based on offline parsers being presented as live success.

## 12. GitHub

Release/commit decision, regression and exact source/dataset checks are recorded in `release_verification.json`. Post-commit HEAD/origin/clean checks and the actual hash are reported after GitHub push. GitHub writes occur only if the requested Stage 76 audit criteria are satisfied; no production-ready claim is made by a source-code commit.

Automatic approval review rejected an attempted change that would disable the external helper's official-host stop guard, because it would weaken the preserved protection/cooldown boundary. The patch was not applied. No equivalent workaround, CAPTCHA bypass or stop-log reset was used.
