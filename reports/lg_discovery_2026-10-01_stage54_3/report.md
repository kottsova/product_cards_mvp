# Stage 54.3 — old parser parity

Дата: 2026-10-01. Статус live gate: ожидает разрешённого Google контроля после действующего HTTP 429 stop (до 2026-10-01T10:24:40.607776+00:00).

## Найденный исходник

`A:\work\dev\load_img\01_search_product_links\find_product_pages\find_product_pages.py`, SHA-256 `6b935c65cb3f03316191fd5e7eaf5679175e5155a35b01cb47108448ef7f119a`. Общий поиск: `google_general_search` (строки 1505–1564), `clean_google_result_url` (1349–1356), `search_global_product_page` (1790–1813), запуск `process_global_google_links` (1888–1962). Отдельный LG mode `process_lg_links` (5003–5043) искал только в KZ sitemap; рабочий общий Google механизм находился в другом режиме того же файла. Исторического лога, подтверждающего находку именно MS2082F старым парсером, не обнаружено.

## Поведенческий diff до переноса

| Old behaviour | Current Stage 54.2 behaviour | Difference | Significance |
|---|---|---|---|
| `p.chromium.launch_persistent_context`, видимый bundled Playwright Chromium, один context для обработки строк | По умолчанию `PlaywrightBrowser` запускает headless Chromium, новый context; после каждого provider query worker сбрасывается | Постоянная сессия против одноразовой | Cookies и состояние Google в старом профиле не попадали в production |
| `user-data-dir=A:\work\dev\load_img\01_search_product_links\find_product_pages\.global_google_profile`, стандартный `Default`; профиль не очищался | У headless worker нет profile. Отдельный Stage 54.1 attended путь использовал `data/browser_profiles/google_search` и `channel="chrome"` | Другой профиль и другой executable в attended режиме | Название «persistent profile» само по себе не обеспечивало parity |
| `headless=False`, viewport `1440×1200`, `--disable-blink-features=AutomationControlled`, без `channel`/`executable_path` | Headless worker без этого flag; attended Chrome видимый, viewport `1400×900`, `channel="chrome"` | Конфигурации Chromium различались | Могла меняться выдача или реакция Google; вклад каждого отличия отдельно не доказан |
| Прямой `https://www.google.com/search?q=<quote_plus(query)>&hl=en`; не homepage, не ввод в поле | Прямой `/search?q=<quote(query)>&hl=en`; также без homepage/typing | Только способ кодирования пробелов (`+` против `%20`) | Гипотеза о старом ручном вводе не подтвердилась |
| Для article MS2082F `site:lg.com "MS2082F"` | Такой же первый запрос; Stage 54.2 допускал более широкий второй | Первый query совпадал по смыслу | Текст запроса сам по себе не объясняет отказ |
| `goto(..., wait_until="domcontentloaded", timeout=60000)`, затем 1000 ms; при challenge до 180 секунд ручного ожидания | Worker deadline 60 s, operation timeout 10 s, DOM projection сразу после навигации; attended путь имел отдельное ожидание | Другая временная схема | Поздняя загрузка/ручное разрешение challenge могли влиять на результат |
| Без scrolling для общего web search | Без scrolling для обычного Google search | Существенного различия нет | Прокрутка в старом файле относится к поиску фото, не PDP |
| `page.locator("a[href]").evaluate_all`: все anchors, `a.href` и `a.innerText`; затем фильтр доменов/служебных URL и dedupe | `browser_projection.js` выбирает result-card links, ограничивает projection и кандидатный список | Старый parser собирал более широкий набор ссылок | Мог поймать PDP, который current projection пропускал |
| `clean_google_result_url`: раскрывает `/url?q=`, декодирует, снимает fragment/query/trailing slash | `_google_target` раскрывает `/url?q=`, остальное сохраняет для последующей проверки | Разная нормализация redirects | Влияет на дедупликацию и форму candidate URL |
| Без `context.route` и лимита ресурсов; обычная сеть Chromium | Host whitelist, блокировка service workers, network cap 200; attended cap 150 | Разный network/browser path | Удалось воспроизвести прежнюю схему без браузерного resource gate |

## Перенос

`product_tool/census/old_parser_google.py` содержит AST-идентичные исходнику функции `google_general_search` и `clean_google_result_url` плюс прежние browser/profile settings. При наличии исходного файла с указанным SHA production вызывает **буквально его** `google_general_search` (проверено: `co_filename` указывает на исходный `find_product_pages.py:1505`); локальная идентичная копия обеспечивает переносимость. Старый `.global_google_profile` используется на месте, без копирования/очистки. На этом компьютере его `Default/Network/Cookies` существует; содержимое cookies не читалось и не выводилось. Пробный запуск без сетевой навигации прошёл: видимый persistent Chromium версии 147.0.7727.15, одна страница `about:blank`, источник функции `original_file`.

`LGBrowserSearch` направляет production Google query в этот driver и возвращает найденные ссылки как кандидатов прежнему `run_web_fallback`. KZ/RU gate, official-domain/product-page/exact identity checks, extraction и readiness не менялись. Bing/DDG из Stage 54.2 остались последующими providers; новых поисковиков нет. На 2026-10-01 10:01 UTC: 133 целевых и cross-stage теста OK, `py_compile` и `git diff --check` OK. Live MS2082F, затем P12ED/S40T и партия ожидают разрешённого контроля Google.

Дополнение к переносу: для quoted `site:lg.com "<article>"` поисковые ссылки теперь проходят также буквальный старый `official_product_candidate` из того же исходного файла; его результат лишь решает, передавать ли ссылку на существующую production-проверку. На тестовом похожем суффиксе старый selector оказался шире строгого variant rule, поэтому его ответ никогда не засчитывается как подтверждение identity. Нерелевантный результат остаётся в trace как `old_parser_result_not_exact` и не расходует лимит PDP validation. После этого изменения: 5 тестов нового модуля прошли.

После дополнительного аудита перенесены также исходные `official_product_candidate` и все используемые им helper-функции/константы. AST десяти поисковых функций локального модуля совпадает с исходником; SHA исходника закреплён проверкой. При отсутствии соседнего исходного файла локальный production модуль сохраняет тот же search/result-screening механизм. Региональный headless browser закрывается перед открытием старого persistent context. Новый офлайн тест проверяет маршрут `old parser result → LGGlobalAdapter exact validation → save_source_document` на вымышленной модели, без прямого URL целевого MS2082F. Текущий локальный набор Stage 54.3: 7 tests, OK.

## MS2082F live: буквальный исходный parser

После истечения Google stop сделана согласованная копия SQLite `data/backups/stage54_3_before_ms.sqlite3` и выполнен один обычный production job `a097fad3e01e4ec9934c6dee12f455f4` (`worker.run_once`, стадии 1/2/3/4/6). Его trace сохранён в `data/attended_capture/stage54_3_ms_job.json`. После KZ/RU miss production вызвал `google_old_parser` с query `site:lg.com "MS2082F"`; trace содержит `mechanism=old_parser_general_search`, `old_parser_source=original_file`, `old_parser_called=true`, `old_parser_completed=true`. Это означает, что в production реально исполнилась функция `google_general_search` из исходного `find_product_pages.py:1505`, в старом `.global_google_profile`, через видимый bundled Chromium. Второй более широкий query того же job также прошёл через неё. Оба вернули `no_candidates`; событий `result` с LG URL нет, поэтому позиция, title и snippet целевого UK PDP не наблюдались и URL не передавался на validation/extraction. Bing в этом job также дал `no_candidates`, DDG — challenge. Это не изменяет вывод о старом Google пути.

В отличие от предыдущих Stage 54.1/54.2 запусков **Google HTTP 429 не было**. Один отдельный, ограниченный диагностический запрос точного query в том же старом профиле (после production job, без нового job) подтвердил: конечный адрес `www.google.com/search`, status HTTP 200, видимый body длиной 2739 символов, 65 anchors и **0 anchors с `lg.com/`**; признаков `unusual traffic`/`not a robot` нет. Метрики без содержимого страницы и cookies сохранены в `data/attended_capture/stage54_3_serp_diagnostic.json`. Следовательно, в этой текущей сессии старый parser не нашёл MS2082F потому, что наблюдаемая Google выдача не предоставила официальной LG ссылки. Исторически работавший механизм и нынешний production путь поискового запроса теперь совпадают; утверждать, что этот старый parser когда-либо находил именно MS2082F, прежних данных недостаточно.

Итог MS2082F: `needs_review` / `not_ready`, 0 facts, 0 photos, 0 documents. Source rows остались KZ/RU `mismatch`, DNS `dealer_url_needed`, Sulpak `unknown`; UK PDP не записан. Сравнение с backup показало те же sources/facts/photos/documents у MS2082F, P12ED и S40T. SQLite до и после: integrity_check=ok, foreign_key_check=0.

## Условные следующие этапы

MS2082F не прошёл обязательный live gate. Поэтому новые jobs P12ED и S40T не запускались; их уже подтверждённые результаты Stage 54.2 сохранены: P12ED — KZ support, NSAR↔USAR, русский manual, непроверенный Sulpak candidate, 0 facts/photos и 1 document; S40T — exact KZ/RU PDP, 62 facts, 63 photo candidates, 1 document, прежний skip внешнего search. Полная партия 12 товаров `ae3d2cb381744ba8a811e54231233254` не перезапускалась. Улучшенных live карточек Stage 54.3 нет.

Stage 54.3 live verdict: **FAIL**. Полный regression suite, commit и push зависят от PASS трёх live controls и не выполнялись. Целевые тесты, `git diff --check` и компиляция проверены; финальный объём тестов указан ниже после итогового прогона.

## Итоговые проверки и Git

Итоговый локальный прогон: 133 targeted/cross-stage tests, OK. `python -m py_compile` для нового модуля/адаптера/тестов прошёл; `git diff --check` прошёл. SQLite integrity_check=ok, foreign_key_check=0. Текущая ветка `main...origin/main`; рабочее дерево содержит незакоммиченные изменения Stage 54/54.1/54.2/54.3. Из-за FAIL обязательного MS2082F live gate полный regression suite, commit и push не запускались. Условие `clean working tree` не выполнено.

Исполняемый файл для старого `p.chromium` в текущем Playwright: `C:\Users\Julynce\AppData\Local\ms-playwright\chromium-1217\chrome-win64\chrome.exe` (существует). Старый код не задавал `executable_path` или `channel`; production old-parser driver повторяет этот способ выбора, что подтверждено запуском Chromium 147.0.7727.15. Отдельный attended transport Stage 54.1 задавал `channel="chrome"` и потому не был тем же запуском.
