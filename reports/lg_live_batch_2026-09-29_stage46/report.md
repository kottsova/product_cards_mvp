# Stage 46 — ручной браузерный режим LG и P12ED

## Причина и прежний механизм

Рабочий старый скрипт находится в `A:/work/dev/load_img/01_search_product_links/find_product_pages/find_product_pages.py`. Для Vseinstrumenti он открывал Playwright `launch_persistent_context` с `channel="chrome"`, `headless=False`, профилем `.vseinstrumenti_profile` рядом со скриптом и viewport 1400×900. При `/xpvnsulc/` в URL он до 120 секунд ждал, пока пользователь пройдёт проверку в Chrome; другая функция также распознавала `/exhkqyad` и `hcheck=`. Cookies сохранялись в профиле и использовались следующим запуском. В старом коде были `--disable-blink-features=AutomationControlled` и исключение `--enable-automation`; они **не перенесены**.

`product_tool/census/browser_worker.py` предназначен для unattended search: headless Chromium, временный context, без профиля, ограниченная сеть, `challenge_detected` закрывает сеанс. Это остаётся правильным для фонового режима. Новый `census/attended_support.py` запускается только явно с `--attended`, открывает обычный Chrome с отдельным постоянным профилем `data/browser_profiles/lg_support`, не нажимает CAPTCHA и не очищает запись об остановке `www.lg.com` в `data/lg_fetch_log.json`. Во время challenge только наблюдает тот же page/context до ручного действия или тайм-аута. Он сохраняет DOM и ограниченные релевантные ответы; cookies остаются в исключённом из Git профиле.

## Доступ и динамические данные

Для одного наблюдаемого адреса `https://www.lg.com/kz/support/product-support/cs-P12ED.USAR/` объявлен лимит: 4 перехода включая ручные, 150 ресурсов, 8 минут ожидания, только `www.lg.com` и `gscs-b2c.lge.com`, без автоматического повтора. Первый видимый сеанс завершился преждевременно из-за ошибки нового условия завершения: конфигурация исходного HTML была принята за загруженный список. Условие исправлено офлайн; одна повторная навигация в том же постоянном профиле дала фактический rendered DOM и API ответ. Challenge в обоих живых сеансах **не появился**, поэтому ручное прохождение проверено только тестом с подставным браузером. Повторов из-за challenge не было. Первый сеанс: 61 разрешённый ресурс; второй: 88 разрешённых ресурсов и 37 отклонённых сторонних ресурсов. Профиль и записи лежат в `data/attended_capture/p12ed_stage46*` и `data/browser_profiles/lg_support` (Git их исключает).

Исходный HTML содержит адрес, заголовок и конфигурацию секции, но не `P12ED.NSAR` и не `Russian`. После JavaScript-render браузер отправил `POST https://www.lg.com/ncms/api/v1/support/proxy/productSupportPage?locale=KZ`, HTTP 200. Именно этот ответ, а не отдельный наблюдаемый `Next-Action` response, дал объект `productSupportPage`; прежнее предположение о видимом server action уточнено фактическим network trace.

| Значение | Точный источник |
|---|---|
| `P12ED` | `productSupportPage.displayModelCode` и видимый `<h1>` |
| `P12ED.NSAR` | `productSupportPage.csSalesCode`, `manualSoftwareList.modelData.csSalesCode`; в rendered DOM — регистрационная ссылка с `csSalesCode=P12ED.NSAR` и breadcrumb `data-modelid` |
| `P12ED.USAR` | `productSupportPage.manualSoftwareList.csSalesCode` в том же официальном ответе; один URL/заголовок не использован как доказательство |
| Список руководств | `productSupportPage.manualSoftwareList.manualList.manualList`: English, Kazakh, Russian |
| Русский документ | запись с `fileNamePrint=Russian`, `originalFileName=Owners_Manual_RU_ERU_R410A_250602_Rev.00.pdf`, `fileName=MgwJVxEROplE6nOrxFymAA` |
| Прямая ссылка | `fileUrl` в API равно `N/A`; rendered DOM напечатал `https://gscs-b2c.lge.com/open/downloadFile?fileId=MgwJVxEROplE6nOrxFymAA` |

Русский PDF по этой прямой ссылке получен одним запросом через существующий `PolicyAwareSession` с лимитом 5 МБ, HTTP 200, 3 079 998 байт, SHA-256 `285b79d592bb2be5f855a9b259bd08784a20857af8c04e42615b771c91939616`. Содержимое: 29 страниц; 22 296 букв русского текста, 9 маркеров инструкции. `P12ED` и полные коды внутри PDF не названы. Связь документа с комплектом подтверждает та же официальная KZ support-страница/API; модельные ссылки внутри PDF сохранены как пустой список. Инструкция не используется для характеристик и фото.

## Рабочая карточка

`LGSupportAdapter` теперь принимает сохранённый официальный API response наряду с rendered DOM; нормальный `run_once()` читает его из snapshot для этой же наблюдаемой support-ссылки, без нового открытия страницы. Сохраняются `support/manual identity` и источник PDF. Отдельный `attended_replay.py` проверил хеши DOM/API/PDF и записал доказательства в **существующий** product 4 партии `ae3d2cb381744ba8a811e54231233254`; не создавал новый товар или задание. Перед записью испытан на временной SQLite-копии; обычный `run_once()` с сохранённым API также проверен на временной базе и не сделал сетевого вызова.

| P12ED | До | После |
|---|---|---|
| Support route | кандидат | официальная связь `P12ED.NSAR` + `P12ED.USAR` для поддержки и руководства |
| Русская инструкция | не проверена | PDF подтверждён по содержимому; в PDF точный код не напечатан |
| Характеристики и фото комплекта | не подтверждены | не подтверждены |
| Статус задания | `needs_review` | `needs_review` |
| Готовность карточки | `not_ready` | `not_ready` |

Причины `not_ready`: нет официальной товарной страницы с полным артикулом комплекта, нет подтверждённых характеристик и фото. Раздел support не переводит техническое задание в `done` и не служит product/spec/photo identity. Карточка и Excel показывают инструкцию, статус задания и готовность отдельно. Остальные строки партии не запускались. Каталог и production-реестр не менялись. Остановка автоматических запросов к LG остаётся в журнале.

## Файлы и миграция

Добавлены `product_tool/census/attended_support.py`, `product_tool/census/attended_replay.py`, `tests/test_attended_support.py`. Изменены `product_tool/adapters/lg_support.py`, `product_tool/worker.py`, `tests/coverage_controls.py`, `tests/test_coverage_queue.py`, `tests/_pipeline_migration.py`. Изменились только данные карточки P12ED в `data/batches.sqlite3` и журнал одного PDF-запроса. Новая миграция Stage 46 и финальные SHA-256 закреплены в `tests/_pipeline_migration.py`: `worker.py` — `b8edf38f80e65d40c1c7ac4307680a4118fc2acd28c955ea010487c925a23aed`; SQLite — `3813d214044b87ffa9180537f315c164a1f854ade318aed6ab533d396ed42922`. Исторические отчёты не переписывались.

## Проверки

Целевые тесты LG support и attended режима: 17 OK до дополнительного worker-теста; новый набор `tests.test_attended_support`: 7 OK. Защитные тесты миграции: 262 OK. Временная и рабочая базы: `PRAGMA integrity_check=ok`, `PRAGMA foreign_key_check` пуст. Число товаров 15, число заданий 34; активных заданий не было. Excel выгружен в память и проверен: строка P12ED показывает `needs_review` и `not_ready`, лист инструкций содержит официальный русский PDF.

Final full regression on the completed Stage 46 files: **1300 tests, OK (707.826 seconds)**. The offline test network guard prevented real site requests.
