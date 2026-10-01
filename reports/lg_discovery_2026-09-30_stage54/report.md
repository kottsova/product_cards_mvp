# Stage 54 — аудит LG discovery по существующей партии

Партия `ae3d2cb381744ba8a811e54231233254`, строки 4–15, 12 товаров. Это **диагностика без изменения поведения**. Для исторической трассы использованы события штатного прогона 2026-09-28 18:30 UTC, сохранённые KZ/RU sitemap и снимки Stage 43, текущие карточки SQLite и код `HEAD 949693352b434b0987bb27f3021cce3975c0815a`. Поздние офлайн-пересчёты Stage 48–50 не названы новым поиском. Историческая полнота выдачи ограничена: production сохранял подтверждённый source и текст причин отказа, но не весь browser result projection. Никакого Google-вызова в текущем LG production path нет.

## Фактический маршрут и запросы

Все строки имеют `brand=LG`. `normalize_lg_sku` удаляет пробелы и переводит код в верхний регистр. Комплект делится на два компонента; `lg_base_model` снимает буквенный суффикс после точки или `_KZ/_SU` только для поиска кандидата. Дополнительный код из описательного `alternate_code` используется только как sitemap fallback. Он не подтверждает вариант. Исключение по формату названия: `MS 2082 F` **не** превращается в поисковый запрос `MS 2082 F`; код строки `MS2082F` остаётся единственным запросом. `ON77DKDRUSLLK` остаётся цельным article; название добавляет sitemap fallback `ON77DK`.

Production сначала загружает `https://www.lg.com/kz/sitemap.xml`, затем `https://www.lg.com/ru/sitemap.xml`. Из них допускает только официальные товарные URL `/kz/...` и `/ru/...` с совпадением ключа последнего сегмента с полным артикулом, базой или моделью из названия (не более трёх URL на ключ). Если результат региона не `full_sku`, браузерный fallback пробует только LG RU support search; для KZ проверенного browser-search route нет. Шаблон реально отправляемого браузерного URL находится в `product_tool/adapters/lg_browser_search.py`: `https://www.lg.com/ru/search/search-support?search={q}&...&oldTerm={q}&...&localeCode=ru...`. `{q}` — значение из колонки ниже, URL-encoded. Это **поиск LG на сайте LG**, не Google. Поиск возвращает максимум три ссылки вида `/ru/support/product/lg-...` и прекращает перебор query после первой непустой выдачи; эти ссылки затем открываются, а напечатанный код сравнивается с артикулом. Support не подтверждает товарные характеристики или фотографии.

| ID | Исходный артикул | Компоненты / base | Дополнительный sitemap key из названия | Реальный browser query Stage 43 |
|---:|---|---|---|---|
| 4 | `P12ED.NSAR + P12ED.USAR` | `P12ED.NSAR`, `P12ED.USAR` / `P12ED` | `P12ED` | RU: `P12ED.NSAR`, `P12ED.USAR`; KZ: route absent; `P12ED` не отправлен после непустых выдач |
| 5 | `S3WER.ALWPCOM` | один / `S3WER` | `S3WER` | RU: `S3WER.ALWPCOM` → `browser_javascript_error`; `S3WER` не отправлен |
| 6 | `MS2082F` | один / `MS2082F` | нет | RU: `MS2082F`; KZ: route absent |
| 7 | `TW4V7EB1W` | один / `TW4V7EB1W` | тот же код | RU: `TW4V7EB1W` |
| 8 | `GC-B459MLWM.ADSQCIS` | один / `GC-B459MLWM` | `GC-B459MLWM` | нет: оба sitemap дали `full_sku` |
| 9 | `VK89309H` | один / `VK89309H` | тот же код | нет: оба sitemap дали `full_sku` |
| 10 | `W4W8LVPKZHM.APBPCOM` | один / `W4W8LVPKZHM` | `W4W8LVPKZHM` | RU: `W4W8LVPKZHM.APBPCOM` |
| 11 | `86NANO81A6A` | один / тот же код | тот же код | нет: оба sitemap дали `full_sku` |
| 12 | `RNC9.DRUSLLK` | один / `RNC9` | `RNC9` | нет: оба sitemap дали `full_sku` |
| 13 | `S40T` | один / `S40T` | тот же код | нет: оба sitemap дали `full_sku` |
| 14 | `ON66` | один / `ON66` | тот же код | нет: оба sitemap дали `full_sku` |
| 15 | `ON77DKDRUSLLK` | один / `ON77DKDRUSLLK` | `ON77DK` | RU: `ON77DKDRUSLLK` при старой identity; после Stage 49 точные PDP означают, что новый поиск уже не нужен |

`Google` для всех 12: **not searched**, следовательно `Google results` для всех 12: **нет фактической выдачи**, а не «Google ничего не нашёл». Dealer search provider также не вызывается. Ограниченные Sulpak-кандидаты для P12ED и S3WER взяты из сохранённых ссылок, не из общего поиска.

## Sitemap → кандидат → решение → карточка

В сохранённых 2026-09-28 sitemap было 3971 KZ и 11343 RU товарных URL после `lg_is_product_url`. Таблица показывает реально совпавший slug и решение исторического штатного прогона. Сокращения `KZ:`/`RU:` в колонке URL разворачиваются в `https://www.lg.com/kz/` и `https://www.lg.com/ru/`. `full` — код основной PDP подтверждён её структурированным полем; `base` — страница не доказывает полный суффикс. Текущее сохранённое состояние указано отдельно от исторического результата.

| Артикул | Sitemap кандидаты и stage-43 outcome | Browser/support candidate outcome | Что дошло до нынешней карточки |
|---|---|---|---|
| `P12ED.NSAR + P12ED.USAR` | KZ 0, RU 0 → sitemap miss | RU support `P12EP...` найден, но на открытой странице другой код; KZ support позже подтверждён отдельным штатным support/API маршрутом | `https://www.lg.com/kz/support/product-support/cs-P12ED.USAR/` — связь компонентов и русский PDF; PDP/spec/photo нет. Sulpak URL лишь кандидат, не запрашивался из-за access-stop |
| `S3WER.ALWPCOM` | KZ `laundry/styler/s3wer/` → full; RU `laundry/lg-S3WER` → base | RU browser query дал `browser_javascript_error`; base query не отправлен | KZ PDP full, RU PDP base; Sulpak кандидат, не доказательство |
| `MS2082F` | KZ 0, RU 0 → sitemap miss | RU support `MS2044V...` найден, открытая страница печатает `MS2044V.BS2QUZB` → identity rejected | Официальной PDP в карточке нет; известный `https://www.lg.com/uk/microwaves/solo/ms2082f/` не поступал в production provider и не проходил identity |
| `TW4V7EB1W` | KZ `laundry/washing-machines/tw4v7eb1w/` → full; RU 0 | RU support `TW4V9RD9E`, `TW4V3RS6W`, `TW4V5EG2S` → напечатанные коды другие | KZ PDP full; RU отсутствует |
| `GC-B459MLWM.ADSQCIS` | KZ `refrigerators/bottom-freezer/gc-b459mlwm/` → full; RU `refrigerators/lg-gc-b459mlwm` → full | Browser не вызывался | Обе PDP; разногласия полей остаются отдельной задачей проверки, не discovery miss |
| `VK89309H` | KZ `vacuum-cleaners/kompressor-vacuum-cleaners/vk89309h/` → full; RU `vacuum-cleaners/lg-VK89309H` → full | Browser не вызывался | Обе PDP |
| `W4W8LVPKZHM.APBPCOM` | KZ `laundry/objet-collection-washtower/w4w8lvpkzhm/` → full; RU `laundry/lg-w4w8lvpkzhm` → base | RU support `lg-W4W8LVPKZHM` → exact support; `lg-W4W8LVPKWHM` → чужой код | KZ PDP full, RU PDP base, точная RU support-связь инструкции |
| `86NANO81A6A` | KZ `tvs-soundbars/nanocell/86nano81a6a/` → full; RU `televisions/lg-86nano81a6a` → full | Browser не вызывался | Обе PDP |
| `RNC9.DRUSLLK` | KZ `speakers/party-speakers/rnc9/` → full; RU `audio/lg-rnc9` → full | Browser не вызывался; исследовательская RU-выдача не является production search для этой строки | Обе PDP; manual exact relation отдельно открыта |
| `S40T` | KZ `speakers/soundbars/s40t/` → full; RU `soundbars/lg-s40t` → full | Browser не вызывался | Обе PDP, RU support; положительный контроль |
| `ON66` | KZ `speakers/xboom/on66/` → full; RU `audio/lg-on66` → full | Browser не вызывался | Обе PDP |
| `ON77DKDRUSLLK` | KZ `speakers/xboom/on77dk/`, RU `audio/lg-on77dk`: Stage 43 видел base; Stage 49 доказал exact через целые структурированные model+suffix tokens | RU support `lg-ON77DK` печатал чужой суффикс `DLVALLK`; `lg-ON66` чужая модель | Обе PDP сейчас full; RU support остаётся family/other variant и не подтверждает exact manual |

Полные URL выше — только наблюдавшиеся sitemap или открытые candidate pages. Строка S40T подтверждает исправный участок `sitemap → PDP → structured identity → source_pages`. Кандидатная RU support-страница не подменяет PDP.

## Что реально вернул browser search и что сохранилось

Исторический штатный прогон сохранил текст решений по открытым RU support URLs, но **не** `BrowserCandidate.label`, полный top N, snippets или query-result JSON. У поисковой страницы LG нет отдельных snippets в проекции, только `title` ссылки. Поэтому ниже различаются production events и отдельная исследовательская проекция Stage 43; последняя не выдаётся за result конкретного job.

| Query / источник | Первые кандидатные URL и title, если сохранены | Решение |
|---|---|---|
| `P12ED.NSAR`, отдельная сохранённая browser projection | `https://www.lg.com/ru/support/product/lg-P12EP.NSJ` — `P12EP.NSJ`; `.../lg-P12EP.UA3` — `P12EP.UA3`; `.../lg-P12EP1.UA3` — `P12EP1.UA3 Кондиционер LG Mega Plus P12EP1 \| Инверторный \| до 35 м²` (всего 6 фрагментов) | Все три top-3 support, RU, `www.lg.com`; исторический production открыл соответствующие страницы с редиректом на `lg-P12EP`/`lg-P12EP1`, напечатанные `P12EP.NSJ`/`P12EP1.NSJ` → identity rejected. Исторический title/snippet не записан |
| `P12ED.USAR`, production event | Те же открытые `lg-P12EP`/`lg-P12EP1` в тексте события; исходные три URL, порядок и title **не записаны** | identity rejected; KZ `cs-P12ED.USAR/` не был result RU provider |
| `MS2082F`, отдельная сохранённая browser projection | `https://www.lg.com/ru/support/product/lg-MS2044V.BS2QUZB` — `MS2044V.BS2QUZB Микроволновая печь LG MS2044V | Соло | 700 Вт | 20 л`; `.../lg-MS2044V.BSSQCIS`, `.../lg-MS2044V.BSSQUZB` — аналогичные MS2044V titles; дальше MS2044V/MS2042DB | Production event доказывает открытый `MS2044V` с напечатанным `MS2044V.BS2QUZB` → identity rejected; title/order production отдельно не сохранены |
| `TW4V7EB1W`, production event | Открыты `https://www.lg.com/ru/support/product/lg-TW4V9RD9E`, `.../lg-TW4V3RS6W`, `.../lg-TW4V5EG2S`; title/order не записаны | Все support RU; printed codes других моделей → identity rejected |
| `W4W8LVPKZHM.APBPCOM`, production event | `https://www.lg.com/ru/support/product/lg-W4W8LVPKZHM` и `.../lg-W4W8LVPKWHM`; title/order не записаны | Первый exact support accepted, второй другой код rejected. RU PDP остаётся base |
| `ON77DKDRUSLLK`, production event | `https://www.lg.com/ru/support/product/lg-ON77DK`, `.../lg-ON66`; title/order не записаны | Support printed other variant/model → exact support rejected; PDP exact подтверждён позже другим evidence |
| `S3WER.ALWPCOM`, production event и сегодняшняя ограниченная проверка | `browser_javascript_error`, результат-кандидат не получен | Техническая остановка. Сегодня выполнена одна из объявленных пяти допустимых навигаций; после ошибки новые обращения к LG остановлены |
| `RNC9`, отдельная исследовательская projection | `https://www.lg.com/ru/support/product/lg-RNC9.DEUSLLK`, `.../lg-RNC9.DRUSLLK`, `.../lg-RNC9.DUKRLLK`; titles содержат соответствующий код и `Аудиосистема LG XBOOM RNC9` | Это **не production browser search** строки RNC9: sitemap уже дал exact PDP |

У всех browser candidates домен `www.lg.com`, регион RU, тип `support page`. KZ support P12ED, UK PDP MS2082F и Sulpak dealer URL не возвращались данным RU provider. Исторические snippets отсутствуют в контракте browser projection, поэтому их нельзя восстановить из SQLite. Полный top N для запросов без сохранённой projection технически недоступен; нельзя честно заполнить его произвольными нынешними результатами.

## Gates и причины потери

| Gate | Наблюдение в этих 12 строках |
|---|---|
| Sitemap / URL pattern | Отбираются только KZ/RU product URLs, последний slug должен равняться lookup key. P12ED и MS2082F не имели такого URL в сохранённых sitemap. UK PDP MS2082F отсекается регионом ещё до fetch. KZ support P12ED не является PDP и исключается из sitemap-кандидатов. |
| Provider priority / early return | Sitemap `full_sku` пропускает browser search (это ожидаемо для 6 строк). Если browser search получил любые первые 3 support results, следующий query по base не отправляется, даже если все три затем отвергнуты по identity. У S3WER ошибка первого full query также остановила base query. Ошибка загрузки sitemap находится вокруг всего `find_source` и пропускает browser fallback; это риск кода, но в сохранённом Stage 43 sitemap отвечал 200, поэтому не назван причиной конкретных 12. |
| Official classifier / product vs support | `www.lg.com` обязателен. Browser provider принимает RU support pattern, а sitemap PDP — только KZ/RU product pattern. Support evidence используется отдельно для manual; product specs/photo не повышаются. |
| Exact/base identity | KZ `data-pim-sku` и RU `data-adobe-salesmodelcode`+suffix проверяются после открытия PDP. URL/title/base не доказывают суффикс. ON77 в Stage 43 ошибочно оставался base из-за форматирования, исправлено в Stage 49; P12ED support kit всё равно не даёт specs/photo. |
| Canonical redirect | P12ED RU support URL с `P12EP.NSJ/UA3` редиректил на `lg-P12EP`; проверялся напечатанный код целевой страницы. Редирект не принимался как P12ED. |
| Saved candidate dedup / overwrite | `source_pages` хранит одну запись на `(product_id, source_key)` и сохраняет last confirmed page при пустом refresh. Это защищает карточку, но полные неотобранные browser results нигде не сохраняются; факты отказа остаются лишь в event/evidence text. Дубликаты редиректов в notes сворачиваются. |
| Access-stop | В Stage 43 Sulpak P12ED/S3WER не запрашивался вследствие ранее установленного stop; это не ответ страницы кандидата. Текущий `data/lg_fetch_log.json` не содержит активного stopped host при этом аудите. Новые синтетические `policy_host_stopped` в более поздних карточках не являются HTTP-ответом LG. |
| Readiness | Следует после discovery/identity. Не объясняет исчезновение URL; `needs_review` и `not_ready` не означают, что поиск не выполнялся. |

## Сравнение со старым `find_product_pages.py`

Исторический файл: `A:/work/dev/load_img/01_search_product_links/find_product_pages/find_product_pages.py`. В нём **несколько режимов**: generic Google и глобальный Playwright search существовали, но LG-specific `process_lg_links()` сам использовал только KZ sitemap. Поэтому нельзя утверждать, что прежний LG mode автоматически выполнял Google fallback.

| Функция | Старый parser | Текущий `product_cards_mvp` | Отличие |
|---|---|---|---|
| Query generation | Generic `search_product_page_url` (175) строил три `site:{domain}` Google-запроса; `search_global_product_page` (1790) — `site:{domain} "{term}"` с Yandex/catalog fallback. LG mode `process_lg_links` (5003) запросов к Google не строил | `lg.py` сначала KZ/RU sitemap; RU `LGBrowserSearch.search` по full/base query на LG support route; Google отсутствует | Реальный production LG не видит индекс Google |
| Модельные варианты | LG `lg_article_lookup_keys` (4940) — полный код и base после буквенного суффикса; без kit decomposition | `lg_article_components`, `lg_base_model`, название как fallback | Комплект сейчас представлен лучше; раздельные знаки `MS 2082 F` из названия не образуют запрос |
| Браузер / профиль | Global search `launch_persistent_context` (1923), видимый Chrome и cookies; у LG mode — `requests` sitemap/PDP | Unattended RU support browser — отдельный headless Playwright worker без persistent profile; отдельный attended support capture (Stage 46) — persistent visible Chrome | Attended capture не является общим Google/PDP discovery |
| Challenge | Старые отдельные браузерные функции могли ждать ручного прохождения; LG mode не имел этого механизма | Unattended search останавливается на challenge; attended support capture запускается отдельно и снимает временный stop только после успеха | Нет автоматического bypass; old manual flow нельзя приписывать старому LG sitemap mode |
| Получение ссылок | LG mode: sitemap KZ, slug match; global mode: search result title/path | Sitemap KZ/RU; browser RU только support links, max 3 | Товарная UK/дилерская ссылка не входит в LG provider |
| Official/dealer filter | Generic Google искал официальный domain, отбрасывал `/support/`; LG mode принимал KZ PDP | Официальные KZ/RU PDP и отдельная RU support identity; dealer только по проверенному известному URL | Нельзя механически объединить результаты разных режимов |
| Регионы | LG mode только KZ; generic global мог искать найденные official domains | LG production KZ/RU, UK нет | MS2082F UK не проверяется текущим LG production |
| Sitemap miss | LG mode завершал строку без страницы | Текущий RU support browser fallback; KZ route absent | Fallback есть, но ищет manuals/support, не PDP и не UK |

## Общие root causes и приоритет

1. **Непокрытый тип поиска:** в LG production нет Google и нет generic PDP search, хотя старый parser содержал отдельный generic mode. RU browser provider ищет только support pages. Это объясняет UK-кандидат MS2082F и отсутствие product-route для P12ED после sitemap miss; не доказывает автоматически, что эти URL появились бы в Google выдаче.
2. **Региональный предел:** KZ/RU product URL gate исключает известную UK PDP до открытия, KZ browser fallback отсутствует. Support URL P12ED, полученный позже иным маршрутом, не может стать PDP.
3. **Остановка на первых нерелевантных support hits:** RU search возвращает максимум три и прекращает query ladder после первой непустой выдачи. В P12ED, MS2082F, TW4V7EB1W найденные страницы имели чужие printed codes; identity обоснованно их отвергла. Базовый query не выполнялся. Это проблема retrieval/ordering, не повод ослаблять identity.
4. **Неполный audit trail:** полные browser projections, titles/snippets, rejected URLs и query timings не пишутся в рабочую SQLite. Поэтому исторический top N всех запросов доказать невозможно. Сегодня один повторный запрос S3WER завершился `browser_javascript_error`; остальные четыре запланированных навигации не запускались согласно правилу остановки.
5. **Отдельные ограничения доступа:** Sulpak candidate P12ED был остановлен внутренней политикой до HTTP; это нельзя считать ни подтверждением, ни отсутствием товара. Исторические проблемы access-stop не объясняют 200-ответы KZ/RU sitemap Stage 43.

Первый слой для следующего изменения — **наблюдаемость существующего discovery**: сохранять ограниченные query/result projections и gate decisions как diagnostics, не меняя принятия источников. Затем на основании полного trace отдельно решать покрытие PDP/регионов и query ladder. Identity, support/spec/photo separation и readiness в этой стадии не менять.

## Критерий Stage 54

**Не PASS:** все 12 строк прослежены через нормализацию, sitemap, исторические принятия и отказы и текущее сохранение, но полный фактический browser top N и titles для нескольких исторических queries отсутствуют в сохранённых данных; повторный ограниченный запрос встретил техническую ошибку до выдачи. Таблица не выдаёт предположения за измерения. Поведение и production-код не менялись; текущая партия и БД не перезапускались. Это диагностический результат, не основание пушить Stage 54 как финальный PASS.


## Сводная матрица по запрошенному формату

Здесь `Google = не запускался` во всех 12 строках. «Принят» относится к PDP или отдельной support-связи, не к готовности всей карточки. Подробные URL и gate приведены выше.

| Артикул | Browser query | Google | Accepted candidates | Rejected candidates | Где потеря | Сохранённый source |
|---|---|---|---|---|---|---|
| `P12ED.NSAR + P12ED.USAR` | `P12ED.NSAR`, `P12ED.USAR` | не запускался | KZ support для manual (поздний маршрут) | RU `P12EP`/`P12EP1` support; Sulpak не запрашивался | product sitemap miss, KZ browser route absent, RU printed-code mismatch | KZ support и dealer candidate; PDP нет |
| `S3WER.ALWPCOM` | `S3WER.ALWPCOM` → ошибка | не запускался | KZ PDP | RU PDP base для точного суффикса; Sulpak не запрашивался | RU browser technical error, RU base-only | KZ full PDP, RU base PDP |
| `MS2082F` | `MS2082F` | не запускался | нет | RU `MS2044V` support | KZ/RU sitemap miss, RU printed-code mismatch, UK вне region gate | PDP нет |
| `TW4V7EB1W` | `TW4V7EB1W` | не запускался | KZ PDP | три чужие RU support pages | RU sitemap miss, printed-code mismatch | KZ full PDP |
| `GC-B459MLWM.ADSQCIS` | не отправлен | не запускался | KZ/RU PDP | нет discovery reject | нет потери discovery | две full PDP |
| `VK89309H` | не отправлен | не запускался | KZ/RU PDP | нет discovery reject | нет потери discovery | две full PDP |
| `W4W8LVPKZHM.APBPCOM` | `W4W8LVPKZHM.APBPCOM` | не запускался | KZ PDP, RU exact support | RU PDP base, support другого варианта | RU PDP suffix mismatch | KZ full PDP, RU base PDP, support |
| `86NANO81A6A` | не отправлен | не запускался | KZ/RU PDP | нет discovery reject | нет потери discovery | две full PDP |
| `RNC9.DRUSLLK` | не отправлен | не запускался | KZ/RU PDP | нет discovery reject | нет потери discovery | две full PDP |
| `S40T` | не отправлен | не запускался | KZ/RU PDP, RU support | нет discovery reject | нет потери discovery | две full PDP и support |
| `ON66` | не отправлен | не запускался | KZ/RU PDP | нет discovery reject | нет потери discovery | две full PDP |
| `ON77DKDRUSLLK` | исторически `ON77DKDRUSLLK` | не запускался | KZ/RU PDP после Stage 49 | RU support чужого суффикса и ON66 | историческая ошибка formatting identity исправлена; manual relation остаётся | две full PDP, family support |

## Проверки и состояние изменений

- `python -m unittest -q tests.test_lg_browser_search tests.test_stage45_lg_route tests.test_stage49_lg_identity`: 17 tests, OK. `pytest` в текущем Python не установлен; здесь используются существующие `unittest` тесты.
- Рабочая SQLite проверена **только чтением**: `PRAGMA integrity_check = ok`; в партии ровно 12 строк.
- `git diff --check`: без замечаний для отслеживаемых файлов; в новом отчёте отдельно проверены UTF-8 и отсутствие trailing whitespace. Production-код, каталог, реестр, база и сохранённые карточки не менялись.
- Отчёт оставлен untracked. Stage 54 не PASS из-за отсутствующих исторических result projections и сегодняшнего `browser_javascript_error`; финальный commit/push Stage 54 не выполнялся.
