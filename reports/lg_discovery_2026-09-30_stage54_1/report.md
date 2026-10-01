# Stage 54.1 — LG discovery fallback: промежуточный результат

Дата: 2026-09-30. **Не PASS.** Код и офлайн-проверки доработаны, но обязательный живой контроль `MS2082F → Google result → UK PDP` не завершён: обычный production browser получил `challenge_detected` на Google. Доступ не обходили и запрос не повторяли. Поэтому текущие 12 строк партии `ae3d2cb381744ba8a811e54231233254` не перезапускались, commit/push не выполнялись.

## Было и стало в коде

Было: KZ/RU sitemap, при неполном совпадении RU support browser search, максимум 3 кандидата, без Google и других регионов. Стало: после недостаточного KZ/RU PDP тот же browser worker может выполнить конечные `site:lg.com` запросы; результат остаётся только кандидатом. Открытый PDP другого официального региона проходит отдельную проверку основного sales code/H1, затем существующие extractors. Неподходящие support страницы больше не обрывают маршрут после третьего результата: предел 8, общий deadline и stop при блокировке сохранены.

Переиспользованы `LGBrowserSearch`, `PlaywrightBrowser`/`browser_worker`, policy-aware HTTP session, LG KZ/RU extractors, support adapter, identity relation и стандартный `run_once()`. Из старого `find_product_pages.py` взята идея общего `site:lg.com` запроса. Старый видимый Chrome с постоянным профилем не переносился: нынешний generic worker остаётся headless и односеансовым; отдельный attended LG support capture не является общим Google discovery. Автоматического CAPTCHA bypass нет.

Добавлена append-only таблица `discovery_trace` для новых jobs: query, provider, время, позиция, title, URL, тип, регион, решение, причина, opened и identity. Snippet записывается, если его предоставляет browser projection; сейчас projection его не возвращает. Для открытых support candidates сохраняется итоговая identity-проверка. Слабый повторный результат не заменяет сохранённый exact PDP; manual/support остаётся отдельным evidence от specs/photos.

## Контрольные товары

| Артикул | Запросы нового builder | Наблюдение в этой проверке | Решение |
|---|---|---|---|
| `P12ED.NSAR + P12ED.USAR` | `site:lg.com "P12ED.NSAR"`; `site:lg.com "P12ED.USAR"`; `site:lg.com "P12ED"` | Новый Google-запрос не отправлялся после challenge на первом контрольном товаре. В рабочей SQLite остаются exact KZ support `https://www.lg.com/kz/support/product-support/cs-P12ED.USAR/`, связь обоих блоков и проверенный русский PDF. Sulpak `https://www.sulpak.kz/g/kondicioneriy_split_sistemiy_lg_p12ednsar___p12edusar` остаётся непроверенным кандидатом. | PDP, характеристики и фото комплекта по-прежнему не подтверждены. |
| `MS2082F` | `site:lg.com "MS2082F"`; из имени `site:lg.com "MS 2082 F"` | Два первоначальных локальных диагностических вызова класса использовали его прежний default whitelist только для LG: `foreign_redirect` был внутренним отказом до навигации. Default приведён к production whitelist. Одна реальная Google-навигация с production whitelist дала `challenge_detected`, результатов нет. По ранее наблюдавшемуся прямому официальному URL `https://www.lg.com/uk/microwaves/solo/ms2082f/` отдельный разрешённый GET получил основной `data-pim-sku=MS2082F.CBKQEUK.EEUK.UK.C`; adapter установил `full_sku`, извлёк 69 raw specs и 36 photo candidates. | UK PDP проходит проверку содержания; фактическое нахождение URL через Google пока **не доказано**. В рабочую карточку это прямое исследовательское открытие не записывалось. |
| `S40T` | `site:lg.com "S40T"` был бы fallback query | Сохранённые KZ `https://www.lg.com/kz/speakers/soundbars/s40t/` и RU `https://www.lg.com/ru/soundbars/lg-s40t` уже имеют `full_sku`; текущий gate не вызывает Google при таком источнике. | Офлайн-контроль пути сохранён, новую рабочую job не создавали. |

Запросы были заранее ограничены: до 3 навигаций Google и до 2 открытий LG PDP, без других хостов. Реально состоялась 1 Google-навигация и 1 LG UK GET. На Google обнаружен challenge; доступ к Google остановлен временной политикой, история сохранена. LG UK не заблокирован. После challenge не было дальнейших Google-вызовов. Sulpak не открывался.

## Проверки и оставшаяся работа

- Новый офлайн-тест: query variants, browser projection, reject первых трёх product/support candidates с принятием четвёртого, `run_once()` с UK candidate, запись trace и сохранение exact evidence.
- Контроль рабочей SQLite: `PRAGMA integrity_check=ok`; 12 существующих строк и карточки не менялись. У `P12ED` manual остаётся в `product_documents`; `S40T` имеет KZ/RU PDP и RU support; у `MS2082F` в production карточке UK PDP пока нет.
- Полный regression: 1358 тестов, 11 failures. Все 11 вызваны только несовпадением закреплённой суммы рабочей SQLite; новых функциональных failures не обнаружено. Отдельная baseline-проверка файла `data/batches.sqlite3` сейчас сравнивает фактический SHA-256 `c70fec2d0c419acdd85405d8e19f58c61b3d5b98e094bb625d4b0d2797974be5` с закреплённым Stage 53.1 `36c1b8156e2f781860566facde0f6cd14d133684e368764bb1cc9dba4636cfef`. БД игнорируется Git и в Stage 54.1 не менялась; контрольную сумму не повышали без отдельного разбора происхождения изменений.
- Новая целевая офлайн-регрессия: 7 тестов, OK; включая штатный `run_once()` с UK candidate и контроль `S40T`, при котором Google не вызывается.
- Для PASS ещё нужен разрешённый реальный Google/browser сеанс после ручного прохождения challenge либо иной наблюдаемый результат существующего провайдера; затем три контрольных товара и только после них прогон 12 существующих строк. Не использовать прямой UK URL как якобы найденный Google результат.

Изменения Stage 54.1 остаются локальными и экспериментальными. Защищённые code-файлы внесены в миграцию с фактическими SHA-256; каталог и production-реестр источников не менялись. Отчёт Stage 54 не переписывался.

## Состояние существующих 12 строк (не новый прогон Stage 54.1)

| Артикул | Последний job status |
|---|---|
| `P12ED.NSAR + P12ED.USAR` | `needs_review` |
| `S3WER.ALWPCOM` | `done` |
| `MS2082F` | `needs_review` |
| `TW4V7EB1W` | `needs_review` |
| `GC-B459MLWM.ADSQCIS` | `needs_review` |
| `VK89309H` | `done` |
| `W4W8LVPKZHM.APBPCOM` | `needs_review` |
| `86NANO81A6A` | `done` |
| `RNC9.DRUSLLK` | `done` |
| `S40T` | `done` |
| `ON66` | `done` |
| `ON77DKDRUSLLK` | `done` |

Это сохранённые статусы прежних запусков, а не результат Stage 54.1. Ни одно из 12 заданий не ставилось в очередь и не выполнялось повторно.
