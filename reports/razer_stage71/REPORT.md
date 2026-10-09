# Stage 71 — Razer live recovery / extraction completion

Audit PASS. **Razer adapter production-ready for controlled use.** Controlled use здесь означает обычную видимую persistent Chrome session, переданную через существующий `adapter_factory` / `RazerAdapter(browser_session=session)`. Это не утверждение о восстановлении raw HTTP/headless storefront и не гарантия ready для любого retail SKU. В frozen наборе 10/10 получают live official data; ready — 7/10, IDs [1, 2, 3, 5, 6, 8, 9]. Неподтверждённые конфигурации остаются not_ready.

Baseline: `61fc1e522a6d336c9509dd0334aeedeb55e2cb05`. Dataset — дословная копия Stage 70; SHA-256 `3165106f1f0ef283c7002d399f5096d4688c20463dd5137cc22f430aae9b08cd`. Ранее закрытые stage reports и frozen inputs не изменены. Общая `razer_identity.py`, readiness thresholds и Razer manual-optional gate сохранены.

## 1. Access / cooldown root cause

Stage 70 storefront ответил main HTTP 403 в 12:19:36 UTC. Ответ имел `challenge_suspected`, а не доказанную CAPTCHA: причина stop — `http_access_denied`, TTL 6 h до 18:19:36 UTC, точный host `www.razer.com`. Support ответил 429 в 12:25:49 UTC: `rate_limit`, TTL 1 h до 13:25:49 UTC, host `mysupport.razer.com`. Это независимые stops; sitemap и document CDN не должны автоматически останавливаться вместе с ними.

Stage 70 guarded 0/10 был выполнен **под активным cooldown**, без десяти новых 429/403 запросов. Это не post-TTL access measurement. Stage 71 `initial_lifecycle.json` в 18:39:59 UTC показывает реально истекшие TTL и пустой active set. История не удалена/не переименована/не состарена искусственно: Stage 70 prefix сохранён.

Предыдущий browser transport пересоздавал ephemeral headless context для каждого search/article; session/cookies не переносились, navigation deadline включал повторный startup. Новый общий read-only `PublicBrowserSession` использует один context, bounded pacing 2 s, operation 10 s, navigation deadline 30 s и ограниченные requests/navigation/DOM. В attended режиме — установленный обычный Chrome, видимый isolated persistent profile, без cookie import, proxy, custom UA или stealth. Profile не попадает в Git. Raw document budget 3 MB исправляет отдельную потерю больших SSR DOM; прежний projection limit не выдаётся за access denial.

403 ancillary resource больше не считается автоматически CAPTCHA document host; main 401/403 остаётся denial. 429 останавливает именно response host. Active stops проверяются до navigation; technical retries после challenge/429 не выполняются. Optional passive `after_manual` observation может добавить auditable success только при новом main 200, ordinary DOM, SHA и той же session; разрешается только temporary challenge/rate-limit, не HTTP denial/manual/fatal. В этих live runs CAPTCHA не появлялась, этот opt-in resolver фактически не понадобился. Его отрицательные controls проходят; реальное ручное решение CAPTCHA не заявлено как протестированное.

Непосредственная причина 403/429 — внешний denial/rate limit. Вклад headless, cookie continuity и server policy нельзя раздельно доказать этим опытом: это не A/B исследование. Доказанный recovery contract — после TTL обычная visible persistent session, без обхода защиты, выполняет два повторяемых live runs. HTTP-only recovery не заявляется.

## 2. Attended / live vs captures

`probe.json`: обычные visible Support searches main 200; initial root capture упёрся в DOM budget и не засчитан как model success. `live_initial.json`: 10/10 новых official sources после TTL, до финальной SSR/gallery extraction. `live_final.json`: 10/10 fresh official navigation/DOM, 208 confirmed specs, 7 ready. `second_live.json`: отдельная browser session, тот же profile, 6 моделей разных категорий. Positive response events, timestamps, session IDs и SHA сохранены в trace/captures.

Каталог использует явно отмеченный 24 h cache; это discovery inventory, не доказательство live PDP. Product/Support HTML каждого live-run получен browser navigation; файлы captures не передаются вместо live transport. `offline_preview.json` — только parser diagnostic. `replay_comparison.json` — отдельная проверка тех же final live bytes: raw/accepted/rejected, identity и photos равны 10/10. Это не десять новых live successes. Системного live/parser divergence на final bytes нет.

## 3. Два exact article

Huntsman: input `RZ03-0339`, `Razer Huntsman Mini [switch=Linear; layout=US]` → official code query `/app/answers/list/kw/RZ03-0339` → printed candidate `Razer Huntsman Mini | RZ03-03390 Support & FAQs` → [article 3609](https://mysupport.razer.com/app/answers/detail/a_id/3609/kw/RZ03-0339). Name/code-prefix match уже поддерживался общей identity; suffix не декодируется. Потеря Stage 70 была на access/fetch после 429, не на identity. Сейчас article live 200, 19 specs и RU guide. Marketing PDP и несколько regions доступны, но не публикуют usable retail variant payload; Linear/US/gallery remain unproved. Article также ссылается на discontinued status. Это не объявляется отсутствием модели.

Barracuda: input `RZ04-0443`, `Razer Barracuda X (2022) [color=Quartz]` → official code query `/app/answers/list/kw/RZ04-0443` → `Razer Barracuda X (2022) | RZ04-04430 Support & FAQs` → [article 6044](https://mysupport.razer.com/app/answers/detail/a_id/6044/kw/RZ04-0443). Stage 70 candidate fetch не завершился при rate limit. Сейчас Support live 200; generation подтверждена Support, Store SSR связывает ту же hardware family с `RZ04-04430300-R3U1`, явным `color=Quartz` и собственным image. Не переносится 2021 model / другой color.

Sitemap loc/valid published hreflang alternate → PDP → official Support search/article. Исправлено отбрасывание корректных GB alternate URLs; malformed repeated locales отклоняются. Catalog query может убрать только parenthesized year для поиска кандидатов, но этот кандидат не проходит identity без hardware/generation evidence. External fallback не нужен для двух articles после successful official search, known article URLs не используются как seeds. Google/Bing challenge/429 по-прежнему требует attended flow и сохранения stop; автоматического CAPTCHA solver нет.

## 4. Retail / color / layout / generation

`ng-state.razerProductMarketingData.variants` читается как опубликованные отдельные nodes: `baseProductName`, literal `code`, `variantOptionQualifiers`, classifications и attached images. Recommendation/footer nodes не являются identity. Retail SKU, hardware model, region URL, color, layout, switch и image relation сохраняются отдельно в `retail_relations`; numeric suffix не используется для вывода color/layout/region.

Model-level facts — только равные значения всех applicable model nodes; differing/missing fields остаются candidates. Configuration подтверждается при совпадении всех requested options, без требования полного input SKU. Keyboard Orange требует явного pre-loaded declaration плюс fully-assembled/tactile node; switch demos/barebones не переносятся. US Layout не приравнивается к UK. Color comparison точная, Phantom White не равен White. Подтверждённая configuration не выставляет `full_sku_confirmed`: это отдельный проверенный bug case общей resolution.

Для parenthesized year Store base name сам по себе недостаточен: нужна связь с exact Support model/hardware. Blade RZ09-0528 не объединяется с RZ09-0581. В актуальном US payload RZ09-0528 nodes — RTX 5060/16 GB/1 TB и RTX 5070/32 GB/1 TB. RTX 5080/32 GB/1 TB у RZ09-0581 — другой hardware, rejected. Hidden `data-arr` остаются candidates; requested/default laptop configuration не подставлена.

GB BlackWidow payload публикует Black US/US(ISO), White US и другие editions/barebones. Exact White+UK relation не найдена; White US, Phantom White и US(ISO) не подменяют её. Подробнее actual nodes в `live_final.json` row 10.

## 5. Headset / SSR extraction

Общий table extractor разворачивает явный rowspan/colspan grid отдельно для каждого table. Continuation td больше не превращается в heading. Колонки/sections сохраняются; malformed spans ограничены. Для explicit `Headphones` / `Microphone` colon-labelled rows component остаётся в attribute name: частотные диапазоны не конфликтуют.

BlackShark 2023 Support raw/accepted: Stage 70 7/5 → Stage 71 16/14. Восстановлены impedance, sensitivity, drivers, earcup dimensions, connectivity/cushions, mic SNR/sensitivity/pattern. Barracuda 2022 exact article теперь получен; его Support и Store SSR раздельно сохранены, итог — 26 confirmed specs. SSR classifications читаются без открытия hidden tabs. JSON-LD и scoped DOM сохраняют свои extraction roles.

Frozen confirmed specs: Stage 70 corrected capture replay 130 → Stage 71 actual live 208. Blade и UK configuration могут иметь меньше accepted facts: changing/different hardware or retail-specific значения удерживаются, coverage не достигается ложным подтверждением. `raw_specs = accepted_specs + rejected_specs` проверено для всех 10; raw labels/values/source roles доступны в JSON. Battery modes/up-to и dimension axes не потеряны.

## 6. Gallery / photos

SSR images привязаны к своим retail nodes. Requested color/layout/switch проверяются отдельно; другой color/layout/edition/barebones — candidate. Одинаковый asset URL не дублируется; более сильная SSR relation повышает existing candidate, не создавая второй image. Introductory image exact Support article допускается как **model render только без requested color/layout**; цвет не заявляется verified, Device Layout — technical diagram, не gallery.

Verified image links: 19 attachments на 8 позициях, включая model render Blade без утверждения requested GPU/RAM/SSD. Все реально скачаны по опубликованным URL, HTTP 200, PNG header/dimensions измерены общим `photo_metadata.image_dimensions`; thumbnails не превращены в invented full-resolution URLs. Размеры 300×300, DeathAdder render 600×628, BlackShark 500×559. Contact sheet визуально проверен; packaging/lifestyle не выбраны как exact product gallery. Цвет Quartz и White видны в реальных renders. Full high-resolution gallery не гарантируется; primary product render достаточно существующему gate.

## 7. Frozen live table

`было live` — Stage 70 final guarded result; `capture` — Stage 70 corrected replay confirmed_specs, не live. `photos` — count identity-approved assets. Для всех manual status Проверена, manual advisory.

| ID | Модель | Было live | Capture specs | Root cause / remaining limitation | Live specs | Photos | Manual | Readiness |
|---|---|---|---|---|---:|---:|---|---|
| 1 | Razer Viper V3 Pro | 0 / not_ready | 19 | session + SSR/gallery | 28 | 6 | Проверена | ready |
| 2 | Razer DeathAdder V3 HyperSpeed | 0 / not_ready | 20 | session; Support model render | 20 | 1 | Проверена | ready |
| 3 | Razer BlackWidow V4 75% | 0 / not_ready | 18 | SSR layout + explicit pre-loaded Orange | 18 | 5 | Проверена | ready |
| 4 | Razer Huntsman Mini | 0 / not_ready | 0 | 429 recovery; retail/layout payload absent | 19 | 0 | Проверена | not_ready |
| 5 | Razer BlackShark V2 Pro (2023) | 0 / not_ready | 5 | rowspan + model render | 14 | 1 | Проверена | ready |
| 6 | Razer Barracuda X (2022) | 0 / not_ready | 0 | 429 recovery; year/hardware join + Quartz SSR | 26 | 1 | Проверена | ready |
| 7 | Razer Blade 16 (2025) | 0 / not_ready | 23 | Support generation join; exact 5080 configuration absent | 15 | 1 | Проверена | not_ready |
| 8 | Razer Wolverine V3 Pro | 0 / not_ready | 8 | SSR classifications/gallery | 22 | 3 | Проверена | ready |
| 9 | Razer Viper V3 Pro | 0 / not_ready | 19 | White retail-node image binding | 33 | 1 | Проверена | ready |
| 10 | Razer BlackWidow V4 75% | 0 / not_ready | 18 | published GB alternate; White/UK combination absent | 13 | 0 | Проверена | not_ready |

Ready IDs: [1, 2, 3, 5, 6, 8, 9]. Not ready: 4 — Linear/US + photo/layout not proven; 7 — exact old-family requested GPU/RAM/SSD absent; 10 — exact White/UK relation/gallery absent. Ни один из этих blockers не связан с отсутствующим manual. Они ограничивают эти строки, а не позволяют использовать соседнюю конфигурацию.

## 8. Manuals

10/10 — **Проверена**. 8 distinct RU User Guide PDFs получены live, bytes/SHA, model text и Cyrillic content проверены, все 8 covers rendered и визуально проверены. User Guide / Master Guide / Quick Start / Safety разделяются по опубликованному title, Safety не принимается за guide. General model guide не утверждает switch/retail-specific configuration. Другие языковые links остаются candidates, не выдаются за verified RU documents. `Проверена, не найдена` применяется только после completed check; техническая блокировка означала бы `Не проверена`. Manual не блокирует readiness.

## 9. Stability / regression / PASS

Second live IDs 1,3,5,6,7,8: source URLs, identity, raw/accepted/rejected specs, photos, manuals и readiness совпали. Нет потери sources и внутрикартовых дублей. Active Razer host stops отсутствуют; новая success session не наследует expired prohibition. Неподтверждённый Blade остаётся not_ready в обоих runs.

Full offline regression: **1691 tests OK**, 600.112 s; source tree unchanged. 31 Stage 71 controls плюс прежние Stage 70/structured-page/access-stop tests покрывают grid, wrong generation/hardware/color/layout/switch, common-vs-variant facts, duplicate promotion, partial config≠full SKU, 200 challenge, main-vs-ancillary 403, exact 429 host scope и guarded navigation. Network guard не снимался. `git diff --check` проходит. Все Stage ≤70 blocks/pins сохранены, authorization/pins Stage 71 добавлены отдельно.

PASS criteria: live official data 10/10 ≥8; missing articles оба найдены; headset recovery сделан; color/layout/configuration не смешиваются; independent live6 стабилен; final live bytes/offline parsing равны10/10; threshold не снижен; regression проходит. **Razer adapter production-ready for controlled use** в описанном visible-session contract. 3 frozen retail configurations остаются not_ready с указанными границами official evidence. Полная внешняя причина прежнего server denial и поведение будущей CAPTCHA не утверждаются как доказанные этим run.

## 10. Git

После этих checks — commit `Stage 71`, push и remote `HEAD == origin/main`, clean working tree. Итоговый hash сообщается после commit: commit не может содержать собственный final hash.
