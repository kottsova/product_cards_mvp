# Stage 7: официальный multi-domain fallback без Chromium

Browser-assisted discovery окончательно исключён из автоматического pipeline. Chromium допускается только как отдельный ручной диагностический инструмент по новому явному запросу пользователя. Stage 7 не вызывает browser strategy, не импортирует browser runtime и не дорабатывает browser-компоненты. Обычный поиск использует только HTTP и сохранённые snapshots.

Исследовательский реестр `product_tool/config/official_domains.v1.json` не заменяет production registry. В нём одна source family имеет несколько записей рынков/доменов с ownership evidence, category/division scope, разрешёнными page/support/document hosts и capabilities. `enabled=false`; `research_enabled=true` разрешает только явно вызванный пилот. Другие рынки не исключаются по стране каталога.

`MultiDomainDiscovery` проверяет основной официальный сайт, затем подтверждённые региональные/global-сайты и соответствующие подразделения. `routed_domains` исключает неподходящие категории: Bosch Home не использует Bosch Tools. Список доменов и порядок фиксируются в scope checkpoint. При раннем исчерпании общего бюджета возвращается `official_search_incomplete`, а не разрешение дилера.

Выбор официального результата: exact_variant, затем exact_model, затем полнота совпавших structured evidence, global при равенстве, затем priority. Региональная exact-страница всегда выше global family-only. Конфликтные результаты не выбираются. Текст и URL используются только для ranking; identity подтверждается существующим structured IdentityVerifier на target page.

`AccessLedger` хранит observation по host, полному endpoint, способу доступа и discovery method. Browser challenge LG из Stage 6.1 относится только к конкретному browser-assisted endpoint. Он не создаёт HTTP pause. Новый HTTP 403/429/challenge временно останавливает точный host для HTTP в текущем запуске; другой host, включая региональный, не блокируется. Разные региональные пути на одном hostname не становятся независимыми host. После HTTP protection не выполняется обход через endpoint того же host. Сохранённые ответы можно анализировать без повторного сетевого запроса.

Бюджеты пилота: максимум четыре официальные domain/market-записи и 40 фактических HTTP-запросов на товар; максимум 10 запросов и 40 секунд на запись, три sitemap-документа, 800 URL, два объявленных безопасных GET query и три target page. Redirect расходует бюджет до запроса и проверяется по allowlist. Ответ ограничен 1 МБ, таймаут запроса 8 секунд, интервал 1 секунда. Новые search/product URLs не угадываются; GET URL формируется только из объявленной безопасной SearchRoute. Результат bounded search не доказывает отсутствие товара во всём мире.

`official_exact_product_not_found` возможен только после рассмотрения всех подходящих записей подтверждённого реестра в пределах бюджета, при наличии доступного discovery evidence и отсутствии незавершённых candidate validations. Если evidence нет — `official_search_unavailable`; если часть доменов не рассмотрена — `official_search_incomplete`. Эти исходы ведут к human review.

`dealer_gate` разрешает только существующую точную allowlist Sulpak для LG: стиральные/сушильные машины, холодильники, пылесосы, микроволновые печи. Сплит-системы остаются review_pending; телевизоры, мониторы, аудио и компьютерная техника не разрешаются. Новые бренды/дилеры записываются в отдельную disabled-очередь с approval_status=review_pending и не участвуют в карточках.

`resolve_card_fields` — контракт будущего объединения полей, а не extractor. Требует source, URL, дату, identity level, extraction method и confidence. Разные variant_key не смешиваются. Дилер дополняет отсутствующее значение, не перезаписывает официальное; расхождение создаёт review. Production cards не изменяются.

Запуск пилота: `.venv\Scripts\python.exe -m product_tool.census.runner_v7`. Результаты и отдельная snapshot DB находятся в `reports/source_census_2026-09-22_stage7/`. Готовый checkpoint не повторяет HTTP. Незавершённая попытка не перезапускается автоматически. Старые отчёты, snapshots, конфигурация и пользовательские изменения сохраняются по SHA-256.
