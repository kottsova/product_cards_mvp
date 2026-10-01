# Stage 54.2 — multi-provider official LG discovery

Дата: 2026-10-01. **BLOCKED**: обязательный MS2082F live gate не нашёл exact official PDP через реально наблюдаемую поисковую выдачу. Commit/push и полный прогон 12 товаров не выполнялись.

## Архитектура

После существующего KZ/RU discovery общий LGBrowserSearch выполняет последовательно Google → Bing → DuckDuckGo через run_web_fallback. Каждый provider имеет свой host access-stop; Google 429/challenge не блокирует Bing/DDG. Stop на provider subdomain относится к тому же provider, но не к другим. После неудачного или успешного запроса browser worker закрывается, чтобы следующий query получил отдельный bounded resource budget; автоматического повторения того же query нет. Single-model query plan: точный site:lg.com с кавычками, затем более широкий site:lg.com CODE LG при отсутствии validated exact. Для комплекта — до трёх component/base queries. URL конкретных моделей в production search logic не добавлялись.

Browser projection распознаёт основную ссылку Bing/DDG result card, сохраняет position, URL, title и видимый snippet; неподходящие результаты остаются диагностикой, а не официальным evidence. DDG human challenge распознаётся из видимого текста страницы. Каждый кандидат проходит прежние official-domain, product-page и exact model/variant checks при открытии страницы. Support/manual не засчитываются за PDP/specs/photos. Пороги readiness и SQLite regression strategy не менялись. Для сохранённого exact KZ/RU PDP worker записывает provider_skip с причиной exact_kz_ru_product_page_present.

## Live control: MS2082F

Production job e582757cae1543afab1dd11425921ac5; обычный worker.run_once, без введённого вручную URL и без preloaded results. Trace сохранён в игнорируемом data/attended_capture/stage54_2_ms_job.json и в discovery_trace.

1. KZ/RU: exact PDP не найден; текущие строки lg_kz и lg_ru — mismatch.
2. Google: query site:lg.com "MS2082F" не отправлялся, потому что сохранялся HTTP 429 stop от Stage 54.1 до 2026-10-01T09:04:31.959019+00:00. Trace: host_stopped, provider_access_stop.
3. Bing: HTTP 200, запросы site:lg.com "MS2082F" и site:lg.com MS2082F LG; оба no_candidates для official LG product/support. Отдельный ограниченный исследовательский query site:lg.com/uk MS2082F также дал no_candidates и не выдаётся за production discovery.
4. DuckDuckGo: первый точный query встретил видимый challenge (HTTP 202 в диагностическом probe), outcome=challenge_detected. Создан только DDG stop до 2026-10-01T09:22:25.259940+00:00; следующего DDG query не было.

Наблюдаемого official LG result для MS2082F нет: URL, позиция, title и snippet целевой UK страницы отсутствуют. Поэтому цепочка result → LG validation → exact identity → extraction не выполнялась. Исследовательски известный UK URL не внесён в результаты, cache или рабочую карточку. Итог: 0 facts, 0 photos, 0 manuals, readiness=not_ready, job status=needs_review. Рабочая база сохранила прежние source rows без exact official PDP.

## Live control: P12ED.NSAR + P12ED.USAR

Production job a40bdd15ec2c4d478b8ac74219833bad. Google и DDG имели независимые активные stops; первый Bing query достиг штатного network resource budget до пригодной проекции, после чего provider flow перешёл далее без повторения запроса. Сохранены exact KZ support https://www.lg.com/kz/support/product-support/cs-P12ED.USAR/, связь support_model=P12ED.NSAR, P12ED.USAR, русский Owners Manual и прежний непроверенный Sulpak candidate. Manual не дал specs/photos: 0 facts, 0 photos, 1 document. Итог needs_review/not_ready. Сравнение с online backup подтвердило те же URL support, dealer и число документов; пустые KZ/RU PDP rows уточнены с unknown до mismatch.

## Live control: S40T

Production job 80ec1cd8f67a4c838a0a91764851f71c. Сохранены exact KZ и RU PDP и RU support. Trace содержит provider_skip: exact_kz_ru_product_page_present; query events Google/Bing/DDG отсутствуют. Итог done/export_ready, 62 facts, 63 photo candidates, 1 document — как в online backup.

## Партия и проверки

Партия ae3d2cb381744ba8a811e54231233254 (12 товаров) целиком не запускалась: MS2082F не прошёл обязательный live gate. Остальные девять товаров не менялись. SQLite после трёх controls: integrity_check=ok, foreign_key_check=0, активных jobs нет.

Добавлены offline regressions: Google 429/challenge → следующий provider; независимые host/subdomain stops; wrong model и family/base reject; support не заменяет PDP; поздний exact result принимается; exact result останавливает следующий provider; bounded query plan без URL special cases; Bing result card/snippet и DDG challenge; S40T skip trace. Целевые и cross-stage migration tests: 109 tests, OK. Полный regression Stage 54.2 не выполнялся, поскольку обязательный live gate BLOCKED. git diff --check прошёл. Исторические migration pins сохранены; для защищённого worker добавлен отдельный Stage 54.2 SHA pin. Commit/push не выполнялись.

## Реальные ограничения providers

- Google: внешний HTTP 429 /sorry/index в Stage 54.1 и действующий на момент job краткоживущий stop.
- Bing: страница доступна (HTTP 200), но три ограниченных MS2082F query не дали official LG кандидата; для P12ED первый query исчерпал network resource budget. Нельзя выдавать пустую или нерелевантную выдачу за validated PDP.
- DuckDuckGo: HTTP 202 с явным human challenge; защиту не обходили, DDG получил собственный временный stop.
- Brave Search: один отдельный исследовательский probe получил HTTP 429 с проверкой бота. В production provider list не добавлен.

## Повторный live контроль после истечения access-stop (2026-10-01)

Создана согласованная резервная копия `data/backups/stage54_2_before_retry.sqlite3` (integrity_check=ok, foreign_key_check=0). Один новый обычный production job `55a2e2d2a2ae4847ae2c7e58cf8f2742` для MS2082F выполнен через `worker.run_once`, без ручного URL или подложенной выдачи. Сохранённый trace: `data/attended_capture/stage54_2_ms_job_retry.json`.

KZ/RU вновь не дали exact PDP. Google при первом запросе вернул HTTP 429 (`/sorry/index`); только для Google установлен rate-limit stop до 2026-10-01T10:24:40.607776+00:00. Bing: точный запрос — `no_candidates`; более широкий запрос первоначально завершился `network_budget_exhausted`. DuckDuckGo показал human challenge; только для DDG установлен stop до 2026-10-01T09:54:49.303080+00:00. Никакого наблюдаемого official LG result для MS2082F, его position/title/snippet и последующей PDP validation нет. Итог job: `needs_review` / `not_ready`, 0 facts, 0 photos, 0 documents. Сравнение с резервной копией подтвердило неизменность source rows MS2082F (KZ/RU mismatch, DNS dealer_url_needed, Sulpak unknown), facts и photos. SQLite после job: integrity_check=ok, foreign_key_check=0.

После анализа браузерного лимита изменена обработка `render_existing_search_result`: лишние subresources отклоняются в пределах прежнего network cap и учитываются как `capped_requests`, но уже загруженный документ выдачи остаётся доступен для чтения DOM; превышение лимита основным document/navigation остаётся ошибкой. Другие режимы браузера сохраняют прежнюю остановку. В trace добавлены `resource_capped` и `network_requests`. Ровно один отдельный Bing-only технический запрос `site:lg.com MS2082F LG` после исправления завершился `no_candidates`, 166 network requests, `resource_capped=false`; официальный кандидат LG так и не появился. Этот probe не является production result и не записывался в карточку.

Добавлен regression test для отклонения лишних subresources при сохранении читаемого документа и отдельный Stage 54.2 SHA pin для изменённого browser worker; исторический Stage 54.1 pin сохранён. Совместный целевой и cross-stage прогон: **126 tests, OK**. `git diff --check` прошёл. P12ED.NSAR+USAR и S40T повторно не запускались: их предыдущие control results приведены выше, а обязательный MS2082F gate остаётся BLOCKED. Поэтому полный 12-product batch, полный regression suite, commit и push не выполнялись. Результат Stage 54.2 остаётся **FAIL/BLOCKED**.
