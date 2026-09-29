# Stage 51.1 — временный access-stop и повтор той же выборки LG

## Причина Stage 51 FAIL

`data/lg_fetch_log.json` — журнал ответов, а не отдельная таблица запретов. Старый `stopped_hosts_from_fetch_log()` превращал **любой когда-либо записанный** 401/403/429 или подтверждённый challenge в бессрочный stop домена. `PolicyAwareFetcher` при создании переносил этот набор в `AccessProbe._stopped_hosts`; `PolicyAwareSession` отказывал до сети. `LGBrowserSearch` читал тот же журнал и имел дополнительный флаг `_stopped_this_run`. В записях были `checked_at` и признак challenge, но не было `reason`, TTL или события разрешения. Поэтому успешный attended Chrome не мог восстановить обычный маршрут. Журнал сохранён; его старые записи не редактировались.

Старый `A:/work/dev/load_img/01_search_product_links/find_product_pages/find_product_pages.py` запускал видимый Chrome с постоянным профилем и до 120 секунд ждал, пока человек пройдёт `/xpvnsulc/` в той же вкладке; cookies оставались в профиле. У него были параметры маскировки автоматизации — они не переносились. Нынешний `attended_support.py` уже имел видимый постоянный профиль и пассивное ожидание, но не связывал успешный результат с access-stop.

## Новый lifecycle

| Причина | Scope и срок | Как завершается |
|---|---|---|
| Подтверждённый challenge | Домен, 30 минут | TTL или успешный attended capture официальной страницы |
| HTTP 429 | Домен, 1 час | Только TTL; attended-сеанс не сбрасывает backoff |
| HTTP 401/403 без подтверждённого challenge | Домен, 6 часов | Только TTL |
| Ручной запрет / технический fatal stop | Домен, без TTL | Не снимаются автоматически; attended-навигация запрещена |

Новые stop-записи содержат `domain`, `reason`, `created_at`, `last_attempt_at`, `scope`, `expires_at`, `source_session`. Старые датированные ответы интерпретируются с теми же TTL; недатированный старый challenge остаётся историей, а не бессрочной блокировкой. История append-only: успешный attended-сеанс добавляет `stop_resolved` только для challenge. Перед каждым HTTP-запросом активный stop перечитывается, поэтому истечение TTL действует даже в уже созданном fetcher. Allowlist, pacing, лимиты запросов и запрет бесконечных повторов сохранены. DNS теперь также сохраняет и читает 401/403/429 в собственном `dns_fetch_log.json`; PDF по-прежнему загружается прежним ограниченным способом.

## Проверка доступа и повторная выборка

Файл [dataset Stage 51](../lg_generalization_2026-09-29_stage51/dataset.json) не менялся: те же 14 каталожных артикулов. На наблюдаемой странице `https://www.lg.com/kz/support/product-support/cs-P12ED.USAR/` выполнен **один** видимый preflight с прежним постоянным Chrome-профилем: 1 навигация, 85 разрешённых ресурсов, 45 сторонних ресурсов отклонено, 3 релевантных ответа сохранено. Challenge в этом живом сеансе не появился. Страница открылась, журнал получил `stop_resolved`, активных LG stop после него нет. Ручное прохождение challenge в том же Chrome-сеансе проверено офлайн-тестом, вживую на этом Stage не потребовалось.

Затем обычный `worker.run_once()` последовательно обработал 14 строк на **отдельной** базе `data/stage51_1_pilot/stage51_1.sqlite3`. Production discovery, extraction и identity не изменялись. Первый объявленный предел — до 6 policy HTTP-запросов на строку, 60 всего — закончился до трёх последних строк. Зафиксирован промежуточный результат `repeat_result_capped.json`; только три строки с ошибкой `[policy_budget_exhausted]` получили второй объявленный лимит 18 запросов. Итого 78 policy HTTP-запросов. Браузерный поиск оставался под своими штатными ограничениями; его ресурсы не входят в число 78. DNS 401 из первого Stage 51 занесён в **изолированный** stop-журнал пилота и не запрашивался повторно. Нового challenge или 429 от LG не было.

В таблице `specs` — разрешённые подтверждённые характеристики; `photos` — подтверждённые галерейные фото **точного** артикула. Число выбранных фото-кандидатов отдельно не повышается до подтверждённых. `RU PDF` означает сохранённое русское руководство с подтверждённой связью; «RU, связь?» — файл найден, но связь с точным вариантом не установлена. «Не проверена» не означает отсутствие на сайте. Полные URL и причины каждого source record есть в `repeat_result.json`.

| Артикул | Stage 51 | После 51.1: official product / support | Specs | Photos | Manual | Задание / карточка |
|---|---|---|---:|---:|---|---|
| F2Y1HS5W.AGWPCOM | needs_review / not_ready | KZ+RU exact / RU base | 118 | 43 | не проверена | needs_review / export_ready_with_gaps |
| W4W8LVPK4HM | needs_review / not_ready | KZ+RU exact / RU exact | 173 | 30 | RU PDF | needs_review / export_ready_with_gaps |
| DC90V9V9W.ABWPCOM_KZ | needs_review / not_ready | KZ+RU base / KZ кандидат | 0 | 0 (48 кандидатов) | не проверена | needs_review / not_ready |
| DC90V5V0W | needs_review / not_ready | KZ+RU exact / RU exact | 67 | 43 | RU PDF | needs_review / export_ready_with_gaps |
| GC-B399SQCL.ASWQCIS | needs_review / not_ready | KZ exact / KZ кандидат | 19 | 14 | не проверена | done / export_ready_with_gaps |
| GC-B509MLWM.ADSQCIS | needs_review / not_ready | KZ+RU exact / RU exact | 49 | 48 | не проверена | needs_review / export_ready_with_gaps |
| 32LQ63006LA.ARUG | needs_review / not_ready | RU base / RU base | 0 | 0 (8 кандидатов) | не проверена | needs_review / not_ready |
| 43NANO81A6A.ARUG | needs_review / not_ready | RU exact, KZ base / RU exact | 64 | 12 (26 кандидатов) | RU PDF | done / export_ready |
| GXDCISLLK | needs_review / not_ready | точная страница не подтверждена / нет | 0 | 0 | не проверена | needs_review / not_ready |
| CL87.DCISLLK | needs_review / not_ready | KZ+RU exact / RU base | 111 | 33 | RU, связь? | done / export_ready_with_gaps |
| VC5316NNTS.APSQCIS | needs_review / not_ready | RU exact / RU exact | 30 | 10 | RU PDF | **error** / export_ready |
| A9K_MAX1 | needs_review / not_ready | точная страница не подтверждена / нет | 0 | 0 | не проверена | needs_review / not_ready |
| MS2044V.BSSQCIS | needs_review / not_ready | KZ+RU exact / RU base | 43 | 18 | RU, связь? | done / export_ready_with_gaps |
| AC09BK | needs_review / not_ready | KZ+RU exact / RU exact | 83 | 42 | не проверена | done / export_ready_with_gaps |

**Сводка:** 10 из 14 получили точную официальную товарную страницу. Готовность: 2 `export_ready`, 8 `export_ready_with_gaps`, 4 `not_ready`. Задания: 5 `done`, 8 `needs_review`, 1 `error`. На четырёх карточках русское руководство связано с вариантом; ещё на двух русский файл найден без доказанной связи. `done` и готовность не смешиваются. Фактов ложного повышения base-фото не обнаружено: у сушилки и 32-дюймового ТВ фото остаются кандидатами; у 43-дюймового ТВ 12 фото точного варианта отделены от 26 выбранных кандидатов KZ.

## Что теперь открыто

- `DC90V9V9W.ABWPCOM_KZ`: официальный сайт показывает базовый код и support-кандидата без каталожного `_KZ`; суффикс не повышен до exact, характеристики и фото точного варианта не приняты.
- `32LQ63006LA.ARUG`: RU товарная и support-страницы относятся к базовому/другому суффиксу; известный DNS URL остановлен после ранее наблюдённого 401.
- `GXDCISLLK`: RU search нашёл support `GX.DCISLLK`, но это не доказывает слитный артикул каталога; товарная страница не подтверждена.
- `A9K_MAX1`: RU search привёл к `A9K-PRO1.AFSQCIS`, другому варианту; перенос исключён.
- В карточках с точной страницей остаются реальные или ещё не разобранные конфликты полей и пробелы manual. Наличие support-ссылки не доказывает инструкцию.
- У `VC5316NNTS.APSQCIS` в обычном пути возникло `sqlite3.IntegrityError` при повторной вставке одного `product_documents.direct_url`. Уже сохранённые данные дают `export_ready`, но **задание завершилось `error`**. Это отдельная общая ошибка сохранения документов для содержательного Stage 51; на Stage 51.1 её не маскировали и код под этот товар не добавляли.

## Файлы и проверки

Изменены общие `product_tool/adapters/policy_fetch.py`, `lg_browser_search.py`, `dns.py`, `product_tool/census/attended_support.py`, одна строка подключения DNS-журнала в защищённом `product_tool/worker.py`; добавлен `product_tool/adapters/access_stop.py`. Добавлены офлайн-тесты lifecycle, обновлены два устаревших тестовых ожидания бессрочного challenge. Исторические отчёты и dataset не переписывались. Изменение защищённого worker описано в `tests/_pipeline_migration.py` с фактическим SHA-256; исходный каталог, production-реестр и рабочая база не менялись.

Целевые офлайн-тесты: 47 OK. Полный regression: **1330 тестов, OK, 600.999 с**. SQLite временной базы: `integrity_check=ok`, 0 нарушений FK, 14 products / 17 jobs (три повторных задания только после budget stop). Рабочая база сохранена с SHA-256 Stage 50 `7abc181e610d0d49c3de74834f61b213cd4abeb16faea55bd1b57b679e4e4d18`.

**Stage 51.1 PASS:** старый challenge больше не блокирует домен бессрочно; официальный LG discovery реально выполнен на всех 14 зафиксированных строках без обхода защиты. Stage 51 снова можно оценивать содержательно, с отдельным разбором четырёх identity/discovery gaps, конфликтов и ошибки сохранения PDF.
