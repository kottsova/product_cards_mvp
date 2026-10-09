# Stage 70 — Razer: PASS (audit)

**Verdict: Razer adapter not ready.** Dataset, first-pass and guarded live results are preserved independently of extraction replay. Stage 70 is an audit PASS, not a production readiness claim.

## 1. Baseline

Обычный неизменённый `run_once()` на HEAD `39f5b3868e5916f0711995468a32b0b34de9f239`: DeathAdder V3 Black, `RZ01-04640100-R3U1`, worker unchanged=True. Получены error/not_ready, 0 facts, 0 photos, DNS dealer_url_needed; Razer dispatch отсутствовал. Model/version V3, Black и R3U1 записаны как исходные/research данные, не как confirmed evidence. Exact PDP/reference Support не передавались worker. Actual queries/events/sources/readiness: [baseline.json](baseline.json). RU manual в baseline не проверен.

## 2. Official source structure

- [Razer robots](https://www.razer.com/robots.txt) объявляет [public sitemap](https://sitemap-xml.razer.com/pro-sitemaps-4237407.php?sn=sitemap1.xml). Два XML fetched HTTP 200 и сохранены в observed; loc содержит family PDP, не гарантированный exact retail SKU. Shared sitemap parser используется для loc; malformed/multiple-locale hreflang alternatives не используются. Catalog cache помечен отдельно в trace.
- [DeathAdder V3 PDP](https://www.razer.com/gaming-mice/razer-deathadder-v3/RZ01-04640100-R3U1): текущий PolicyAwareSession получил HTTP 403. Stop сохранён; browser storefront bypass не выполнялся. Встроенный Codex browser оказался недоступен, поэтому применён имеющийся project Playwright transport.
- Прежний Stage 12 public census подтверждает SSR hydration, Product JSON-LD и PRIMARY/GALLERY media. Это структурное историческое evidence; не выдаётся за новый live capture. Store XHR/embedded state не проверены live за 403, отдельный API не выдуман. JSON-LD Product и dedicated technical tables поддержаны минимальным adapter; полный SSR coverage остаётся gap.
- [Razer Support](https://mysupport.razer.com/) загружен ordinary browser, сохранился public HTML. Собственный handler Search Support публикует `/app/answers/list/kw/{terms}`; article IDs выводятся из результатов, не seeded URLs. HTTP на article возвращает pre_page_check shell; normal JS render способен получить article, не выполняя challenge algorithm вручную.
- В [Support baseline](https://mysupport.razer.com/app/answers/detail/a_id/6124) #at-a-glance отделяет technical table от FAQ/warranty/compliance. Documentation table связывает User Guides, включая RU, с моделью. Global compliance/footer PDF исключены. Manual является model-level, не proof цвета/layout/SKU.

## 3. Identity and RZ findings

Наблюдаемые префиксы: RZ01 — мыши, RZ03 — клавиатуры, RZ04 — гарнитуры, RZ09 — Blade, RZ06 — controller. Это наблюдения sample, не универсальный decoder. Printed model code имеет разную длину (например, DeathAdder V3 RZ01-04640), иногда trailing x у Blade. Полный commercial part, hardware/model code и regional suffix — разные поля. Близкий код сам по себе не exact: требуется точное commercial name с generation/connectivity; допускается лишь model-level связь опубликованного code family при том же имени. R3U1/R3M1/R3W1 не декодируются в цвет/layout/регион без отдельного официального evidence. Ни один frozen input не содержит выдуманного полного retail SKU.

Exact retail подтверждение требует одного coherent JSON-LD Product с возвращённым полным part и именем. Запрошенные color/layout/switch/region/GPU/RAM/storage дополнительно сверяются с явными полями. Другой suffix, варианты, default selector и несколько Product blocks не становятся exact. Model specs не требуют полного part. Resolution источники razer_model/razer_configuration остаются раздельными.

## 4. Discovery and live stability

Порядок: regional exact feasibility → published catalog → loc other regions → own Support search (code, затем commercial model при miss) → существующий общий Google/Bing browser fallback → DNS dealer. Ни одного product/article URL seed в production adapter. Trace содержит query/provider/URL/region/type/decision/reason/relation. Regional exact published route не найден; requested-region ranking и SKU suffix relation пока требуют доработки.

Первый live worker прогнал все 10. У 7 позиций был captured official model source; у каждой job error из-за пропущенного обязательного timestamp dealer trace. Ошибка исправлена. Начальный parser также терял code families с дополнительным printed digit и common programmable controls (RAM substring). Сохранён исходный результат без перезаписи.

Interim corrected live сохранил 10 строк. После обнаруженных Support 429 audit-процессы остановлены, затем установлен общий cooldown. Ранний adapter останавливал один browser, но не переносил rate limit в общий host cooldown; это системный root cause повторных обращений. Он исправлен: actual 429 append-only → access_stop; следующий render не создаёт driver. Historical errors не удалены. Финальный guarded live всех 10 проверил host_stopped без новых 429 и дал 0/10 ready, 0 newly confirmed specs. Replay это не маскирует.

## 5. Extraction and configuration protection

Raw section/label/value хранится до mapping. В capture replay финального кода 8/10 model identities, 130 confirmed specs. Raw partition принят/отклонён полностью согласована. Model lookup не подтверждает color/layout/bundle/switch или laptop SKU.

- В Blade #at-a-glance содержит hidden data-arr по GPU/CPU/RAM/storage. Все selector values отклонены, даже default visible. Installed/upgradeable/power adapter/box/material и configuration dimensions/weight остаются кандидатами. 24 из 48 raw rows отвергнуты. Только общие model facts использованы; не смешаны GPU/RAM/storage.
- Viper runtime — четыре отдельных максимума: 1000/2000/4000/8000 Hz; сохраняется Up to/«До». Headset 70 h имеет «режим не указан», ему не назначается Bluetooth/2.4 GHz самовольно. Фото другого цвета/layout — candidates; URL heuristics различают accessories/lifestyle, но полноценная product render/device layout/gallery classification ещё не подтверждена live. Ни одного выбранного verified фото в sample.
- Dimensions Length/Width/Height и L/W/H в мм сначала проверяются с явными осями; L мыши переводится в глубину. Затем используются общие canonical axis/weight normalization. Blade с изменяемыми hardware dimensions консервативно исключён. Long axis names не перепутаны с дюймами.
- Headset continuation/rowspan markup обрабатывается неполно: реальные drivers/impedance/weight находятся в capture, но общий table parser часть continuation rows воспринимает как headings. Это extraction gap, не отсутствие спецификаций. SSR/XHR live coverage также не заявлен.
- Warranty/software fields исключены, description Support остаётся пустым; firmware/Synapse setup/pairing/reset/repair инструкции в commercial description не включаются.

## 6. Frozen dataset and first-pass table

Eight distinct models + two deliberately complex color/layout positions, frozen after baseline before adapter run. SHA-256: `3165106f1f0ef283c7002d399f5096d4688c20463dd5137cc22f430aae9b08cd`. [frozen_inputs.json](frozen_inputs.json). Catalog/model codes намеренно не обозначены retail SKU.

| ID | Input / requested variant | First live specs / job | Corrected capture specs / job | RU manual | Ready | Main remaining gap |
|---|---|---|---|---|---|---|
| 1 | Razer Viper V3 Pro / RZ01-0512 | 15 / error | 19 / done | Проверена | not_ready | verified gallery |
| 2 | Razer DeathAdder V3 HyperSpeed / RZ01-0514 | 0 / error | 20 / done | Проверена | not_ready | verified gallery |
| 3 | Razer BlackWidow V4 75% [switch=Orange; layout=US] / RZ03-0500 | 16 / error | 18 / done | Проверена | not_ready | gallery + exact configuration |
| 4 | Razer Huntsman Mini [switch=Linear; layout=US] / RZ03-0339 | 0 / error | 0 / needs_review | Не проверена | not_ready | exact article not captured; discovery/429 |
| 5 | Razer BlackShark V2 Pro (2023) / RZ04-0453 | 5 / error | 5 / done | Проверена | not_ready | verified gallery |
| 6 | Razer Barracuda X (2022) [color=Quartz] / RZ04-0443 | 0 / error | 0 / needs_review | Не проверена | not_ready | exact article not captured; discovery/429 |
| 7 | Razer Blade 16 (2025) [GPU=RTX 5080; RAM=32 GB; storage=1 TB] / RZ09-0528 | 41 / error | 23 / done | Проверена | not_ready | gallery + exact configuration |
| 8 | Razer Wolverine V3 Pro / RZ06-0520 | 8 / error | 8 / done | Проверена | not_ready | verified gallery |
| 9 | Razer Viper V3 Pro [color=White] / RZ01-0512 | 15 / error | 19 / done | Проверена | not_ready | gallery + exact configuration |
| 10 | Razer BlackWidow V4 75% [switch=Orange; layout=UK; region=en-GB; color=White] / RZ03-0500 | 16 / error | 18 / done | Проверена | not_ready | gallery + exact configuration |

Все 10: guarded live 0 new specs/not_ready; capture replay также 0 ready. First live и replay — разные измерения, числа extraction не претендуют на live repeatability. Dealer actual traces сохранились; exact regional commercial code не подтверждён. Replay dealer network не выполнялся.

## 7. Manuals

8 позиций: Проверена (6 разных RU User Guide PDF, SHA-256 и model text checked; все 6 covers rendered). Huntsman Mini/Barracuda X: Не проверена, exact article не получен. Проверена, не найдена используется только после завершённой проверки; техническая блокировка не выдаётся за отсутствие документа. Safety/Regulatory не принимается за User Guide. Manual optional в readiness; это отдельно проверено тестом.

## 8. Edge cases

27 offline controls: same model/other color, US vs UK layout и фото, switch options, wired/wireless, поколения, другой regional suffix, multiple JSON-LD Product, hidden laptop selector, батарея по polling mode, product dimensions, host allowlist, persistent 429, snapshot challenge/DOM/mode budgets. Другой цвет/раскладка/CPU/GPU/RAM/storage не confirmed. Source-specific extraction scopes и общая resolution достаточны для защиты; synthetic exact-gallery control положителен, actual sample galleries не подтверждены.

## 9. UI / Excel

10 native product pages HTTP 200; Russian canonical labels, parent groups/core/features, отдельные candidate/configuration sections, battery modes, widths/heights/depths, three manual states и descriptions проверены. Native export использует существующий exporter. Readiness/variants/candidates/documents/raw-facts/photo-candidates sheets созданы, Excel formula errors отсутствуют. UI проверяется на explicitly replay DB, не изображает актуальный live success.

ArtifactTool выполнил read-only import/inspection и сохранил три PNG. После render Windows native process завершился -1073740791; fault сохранён как limitation, не замаскирован успешным exit. Native workbook contents проверены независимо. У длинных полей current row/column layout ещё есть clipping в render; полный текст остаётся в cell. Это presentation gap к controlled use.

## 10. Architecture conclusion

Razer укладывается в общий pipeline с небольшим brand adapter. Отдельный framework сейчас не нужен. Existing identity scopes + conditional field filtering защищают конфигурацию; следующий этап должен улучшить shared rowspan/section extraction, exact retail discovery/SSR payload, scoped gallery и live Support transport stability. Самостоятельный configuration-resolution layer заранее не требуется.

## 11. Regression and verdict

Regression: {'exit_code': 0, 'source_tree_unchanged': True, 'elapsed_seconds': 628.9239197000279, 'result': ['Ran 1660 tests in 625.162s', 'OK'], 'command': 'A:\\work\\dev\\product_cards_mvp\\.venv\\Scripts\\python.exe -m tests', 'network': 'offline test guard'}. Earlier stage reports/datasets/pins не изменены; Stage 70 authorization добавлена отдельно. `git diff --check` выполнен; final commit/push выполняются после PASS.

**Razer adapter not ready.** Blockers: storefront 403, Support 429/live repeatability, two uncaptured exact models, unproven regional/retail identity, no verified scoped photos, incomplete headset/SSR extraction and long-field Excel layout. Ни один manual gap readiness не блокирует.

## 12. Git

Commit: Stage 70. Final hash/HEAD==origin/main/clean tree are verified after commit and reported in the final response (a commit cannot contain its own final hash).
