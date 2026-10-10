# Stage 72 HyperX baseline audit

**Audit PASS. HyperX adapter not ready.** Общий pipeline переносится на HyperX с небольшими brand route/parser/presentation bindings. Отдельный configuration-resolution framework не нужен. Последний actual live-run получил official data для 5/10, предыдущий actual live-run — 10/10 (9 exact retail configurations). HTTP 429 и сохранённый cooldown препятствуют controlled production use. Offline parser на сохранённых ответах — отдельный режим, не live success.

## 1. Baseline до изменений

Обычный `worker.run_once(database)` без injected adapters, URL или модели в новом коде: QuadCast 2 S Black, `9A273AA`. Использована уже существовавшая Stage 15 KNOWN_URLS запись, а не новый discovery результат. PDP HTTP 200: https://hyperx.com/products/hyperx-quadcast-2-s-usb-microphone . Identity `exact_variant`, job `done`, readiness `not_ready`; 13 raw facts, 9 gallery renders и 5 feature images по старому parser. Color Black опубликован variant record; regional suffix/revision отсутствуют; commercial model QuadCast 2 S не равен QuadCast 2. Query variants не исполнялись: legacy lookup обходил discovery. Manual не проверена. DNS получил 401 и остановился без обхода.

Root causes: readiness учитывал только LG OFFICIAL_KEYS; HyperX exact_variant попадал в generic official_base_only; photos не выбирались; parser сохранял Unit price. Default response cap 512000 bytes ограничивал полноту payload. Baseline raw HTML, исходные jobs/facts/photos/evidence сохранены, исходный результат не переписан.

## 2. Official структура

`hyperx.com` — Shopify storefront. Homepage объявляет GET `/search` (`q`, `type=product`, `options[prefix]=last`). Robots объявляет sitemap index и product sitemap; 200 ответы сохранены. JSON-LD Product даёт selected SKU, offers, merchant GTIN и numeric Shopify productID. `script[data-product-json]` содержит option-labelled variants и media. Explicit `table.tech-specs-table` и technical tab дают section/raw label/value. Gallery и feature infographics разделены.

Footer `/pages/support` публикует https://supportcenter.hyperx.com и отдельно HP support для OMEN PCs/monitors. HyperX accessories обслуживает собственный Support Center (Sprinklr SSR/JS), не автоматически HP product support. Категории Headset/Keyboard/Mouse/Microphone/Controller получены live 200. SSR показывает десять популярных articles на категорию. Search link существует, но executable query parameter не объявлен в HTML; полный model/manual inventory требует browser/API binding. HP newsroom и официальный HyperX press содержат отдельные part-number tables. Published guide download host — `files.hyperx.com`.

Other-region roots остаются independent official candidates. В observed frozen run региональное расширение не было выполнено до конца в 20-секундном official budget; отсутствие RU retail payload не объявляется отсутствием товара. Общий Google browser fallback после exact official miss вызван отдельно: `no_candidates`; полноценный successful search response этим результатом не доказан. Product-only filters также не заменяют чтение press identity relations. Dealer fallback общий DNS, 0 accepted dealer sources; seeded retail URLs не добавлялись.

## 3. Identity и part numbers

Model-level характеристики разрешены при exact commercial model, включая поколение и wired/wireless qualifier. Exact full code не нужен для общих model facts. Variant-specific color/layout/switch/physical configuration переносится только при подтверждённом выбранном variant; его Shopify record и JSON-LD offer должны иметь связанный SKU/variant ID. Selected default и другой вариант не подставляются. Explicit requested options сопоставляются отдельно; SKU/name disagreement отвергается.

Merchant SKU, HP part number, Shopify product ID и Shopify variant ID — разные relations. `#suffix` хранится буквально, без декодирования layout по суффиксу. Revision не выводится из похожего кода. В `part_number_findings.json` сопоставлены HP `Part Number` и **historical Stage 18** HyperX merchant records для Cloud III wired; этот контроль не выдаётся за fresh discovery. Cloud III Wireless `77Z46AA` не подменяется wired `727A8AA`/`727A9AA`.

Официальная HyperX [press table](https://hyperx.com/blogs/press/hyperx-alloy-origins-65-mechanical-gaming-keyboard-now-shipping-with-colorway-customizations) публикует `4P5D6AX#ACB` — Russian, Red; `4P5D6AA#ABA` — US Red; `56R64AA#ABA` — US Aqua. Это доказательство опубликованных part/configuration relations, не текущей availability и не RU gallery. [HP Cloud III press](https://www.hp.com/us-en/newsroom/press-releases/2023/hyperx-announces-cloud-iii-gaming-headset.html) — отдельный источник manufacturer part facts.

## 4. Frozen dataset и первый pass

10 строк зафиксированы до первого run. SHA256 `0e82e7604f60203f41ae326de0fc76e224f78a614f2123c1bf3e474c6707615f`. 3 гарнитуры, 3 keyboard configurations (в том числе сложный RU SKU), 2 мыши, микрофон и controller. Baseline `9A273AA` исключён из десятки. В input нет PDP URLs. Dataset после freeze не менялся. Первый обычный pass: 1/10 official source, 0/10 ready; причина остальных — отсутствие старого KNOWN_URLS route. Новая discovery использует published forms/sitemaps и shared parsers, а не model URL hardcode.

## 5. Последний actual live-run

| ID | Входной SKU | Commercial model / configuration | Первый pass | Live confirmed specs | Exact gallery links | Job | Readiness | Главный gap |
|---:|---|---|---|---:|---:|---|---|---|
| 1 | AJ5C7AA | HyperX Cloud Alpha 2 Wireless | official URL needed | 28 | 10 | done | export_ready | — |
| 2 | 7G8F3AA | HyperX Cloud Mini Wired | official URL needed | 14 | 6 | done | export_ready | — |
| 3 | 77Z46AA | HyperX Cloud III Wireless | exact / 23 raw facts | 19 | 7 | done | export_ready | — |
| 4 | 7G7A4AA#ABA | HyperX Alloy Rise 75 [color=Black;layout=US Layout;switch=HyperX Red - Linear] | official URL needed | 19 | 5 | done | export_ready | — |
| 5 | 56R64AA#ABA | HyperX Alloy Origins 65 [color=Black;layout=US Layout;switch=HyperX Aqua - Tactile] | official URL needed | 20 | 1 | done | export_ready | — |
| 6 | 6N0A7AA | HyperX Pulsefire Haste 2 Wired | official URL needed | 0 | 0 | error | not_ready | 429 / active cooldown |
| 7 | 6N0A9AA | HyperX Pulsefire Haste 2 Wireless | official URL needed | 0 | 0 | error | not_ready | 429 / active cooldown |
| 8 | 872V1AA | HyperX QuadCast 2 [color=Black] | official URL needed | 0 | 0 | error | not_ready | 429 / active cooldown |
| 9 | 6L366AA | HyperX Clutch Gladiate Wired | official URL needed | 0 | 0 | error | not_ready | 429 / active cooldown |
| 10 | 4P5D6AX#ACB | HyperX Alloy Origins 65 [color=Black;layout=RU Layout;switch=HyperX Red - Linear] | official URL needed | 0 | 0 | error | not_ready | 429 / active cooldown |

Manual status всех десяти: `Не проверена`. Dealer confirmed: 0. Gallery counts означают identity-scoped links из actual PDP; не скачанные/byte-verified images. Image measurement attempts остановлены общим действующим HyperX cooldown: 0 byte-verified images. Разные color/layout остаются candidates. Existing photo selection сохраняется при повторной обработке.

Предыдущий independent actual live run (`live_final.json`, до support completion) получил 10/10 model sources, 9/10 exact configuration и 9/10 ready. Его sources:

- ID 1: https://hyperx.com/products/hyperx-cloud-alpha-2-wireless-gaming-headset — model_confirmed, exact_variant
- ID 2: https://hyperx.com/products/hyperx-cloud-mini-wired-headset?variant=45662621073565 — model_confirmed, exact_variant
- ID 3: https://hyperx.com/products/hyperx-cloud-iii-wireless-gaming-headset — model_confirmed, exact_variant
- ID 4: https://hyperx.com/products/hyperx-alloy-rise-75-mechanical-gaming-keyboard — model_confirmed, exact_variant
- ID 5: https://hyperx.com/products/hyperx-alloy-origins-65?variant=42329903988893 — model_confirmed, exact_variant
- ID 6: https://hyperx.com/products/hyperx-pulsefire-haste-2-gaming-mouse?variant=43416224006301 — model_confirmed, exact_variant
- ID 7: https://hyperx.com/products/hyperx-pulsefire-haste-2-wireless-gaming-mouse?variant=43416225153181 — model_confirmed, exact_variant
- ID 8: https://hyperx.com/products/hyperx-quadcast-2-usb-microphone?variant=45776721051805 — model_confirmed, exact_variant
- ID 9: https://hyperx.com/products/hyperx-clutch-gladiate-wired-xbox-gaming-controller — model_confirmed, exact_variant
- ID 10: https://hyperx.com/products/hyperx-alloy-origins-65 — model_confirmed, unverified

`offline_parser.json`: current parser на тех же saved bytes, 157 confirmed specs, 9/10 ready. Это не новый live-run. Partition raw=accepted+rejected проверен для всех 10. Последний actual live — 100 confirmed specs в 5 доступных карточках. Сводка не смешивает эти режимы.

## 6. Extraction, edge cases и UI/Excel

Component/block labels сохраняются до canonical mapping. Headphone/microphone sensitivity больше не конфликтуют; keyboard general actuation description и switch actuation distance — разные ключи. Published Aqua/Tactile vs Operation Style Linear на Origins 65 отвергнут как source contradiction. Unit price исключён. Weight с headset/base station/boom mic и microphone/stand не сворачивается в вес устройства; source ownership остаётся в значении. Dimensions сохраняют опубликованные axes, Length не становится Depth автоматически. Runtime `Up to` остаётся заявленным максимумом; неизвестный режим не превращается в 2.4GHz/Bluetooth/RGB claim. Missing sample-rate/bit-depth table coverage не восполняется marketing description.

23 meaningful offline tests: other color, US/UK/RU, wrong switch, wired/wireless, wrong generation, nearby part, Shopify numeric ID≠HP part, literal suffix, other-selected physical specs, vendor contradiction, price, metadata≠spec coverage, manual optional, shared discovery links, cooldown/no network/log preservation, UI/Excel read-back. Configuration facts из family options не становятся confirmed. Время и основная часть runtime не подтверждаются по footnote без явного mode relation.

UI HTTP200 read-back для доступных и blocked карточек, separate identity/options/candidates/documents, Russian canonical labels и parent groups. Core/features разнесены; ошибочная LG caption убрана. Excel read-back: product category sheets, sources, photos, HyperX readiness, identity relations, rejected facts, typed documents и photo candidates. Support/help content не используется как description: только PDP description, support отдельно.

## 7. Manuals

User Guide/Master Guide/Quick Start/Safety/Warranty различаются по типу; Safety не считается User Guide. Для ID4 найден опубликованный [Quick Start article](https://supportcenter.hyperx.com/articles/alloy-rise-75/hyperx-alloy-rise-75-quick-start-guide/68d6a88d1498c079f6b362f2) и PDF link. Supplementary bounded download: `Network request failed`; PDF/model/RU content не проверены. Этот сбой не называется доказанным серверным 403/429. Полный manual inventory не завершён, поэтому нет ложного статуса «Проверена, не найдена». Manual optional и не блокирует readiness.

## 8. Access lifecycle и verdict

HyperX PDP ID6 в финальном run вернул 429 at `2026-10-10T11:34:27Z`. Existing domain cooldown `hyperx.com`, TTL1h, expires `2026-10-10T12:34:27Z` (16:34:27 Asia/Tbilisi). Stops/history не удалены и timestamps не состарены. После correction active stop становится `blocked`, не `official_url_needed`. Guarded check: 0 requests, log unchanged. Не изолировано, какой вклад внесли server policy, повторные проходы и новые HTTP sessions; rate-limit response доказан, причинный A/B не заявляется. No CAPTCHA bypass/automatic solution; CAPTCHA completion не испытывалась.

**HyperX adapter not ready**: (1) unstable HTTP access/429 и active cooldown; (2) текущая exact RU PDP/gallery relation не разрешена в bounded official path; (3) full support inventory/browser/API/manual retrieval integration не завершён; (4) runtime mode/footnote и sparse microphone table coverage требуют дальнейшего extraction audit. Manual absence само по себе не блокер карточки. Для identity/configuration нужен существующий общий слой плюс brand bindings, отдельный framework не обоснован.

## 9. Regression и Git

Regression: `['Ran 1714 tests in 562.934s', 'OK']`; exit `0`, source tree unchanged `True`. Earlier stage blocks/pins сохранены; Stage72 authorization append-only. Прерванные pre-UI/pre-label/pre-import checks сохранены отдельно и не считаются regression PASS. `git diff --check` выполнен. После audit PASS — commit `Stage 72`, push, actual remote hash equality и clean working tree; окончательный hash сообщается после commit.
