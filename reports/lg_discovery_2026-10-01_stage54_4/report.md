# Stage 54.4 — официальный LG sitemap discovery

Дата: 2026-10-01. Партия: `ae3d2cb381744ba8a811e54231233254`.

## Фактическая инфраструктура LG

- `https://www.lg.com/robots.txt` (HTTP 200) объявляет `https://www.lg.com/sitemap.xml`.
- Root sitemap — `sitemapindex` из 80 региональных индексов. Среди них KZ (`/kz/kz-gpone-index.xml`), RU (`/ru/index.xml`), UK (`/uk/uk-gpone-index.xml`). Все три ответили HTTP 200; в KZ/RU индексах по 4 дочерних sitemap, в UK — 6.
- UK `/uk/sitemap.xml` — `urlset` с 10 463 URL и 858 580 байт. По нормализованному токену `ms2082f` найден `https://www.lg.com/uk/microwaves/solo/ms2082f/`. Эта находка получена сканированием URL официального sitemap, без открытия всего набора PDP. В UK `/uk/uk-pdp-sitemap-hreflang.xml` (3165 `loc`) нужного пути нет; поэтому нельзя ограничиваться только PDP/hreflang sitemap.
- В исследованных root, KZ, RU и UK индексах ссылок `.xml.gz` не было. Production parser поддерживает их при появлении. Фактические статусы, размеры, `loc` и дочерние URL сохранены в [sitemap_research.json](sitemap_research.json).

## Production flow

`KZ/RU exact PDP` → при miss `robots.txt` → root sitemap index → региональный index → URL sitemap → нормализованный индекс slug/model → обычная проверка официального PDP и точного основного кода модели → извлечение → только при miss web search.

`product_tool/lg_sitemap_discovery.py` обходит только официальные XML URL, объявленные LG, ограничивает обход 8 сетевыми запросами, 5 регионами, 8 кандидатами, 25 МБ распакованного XML и общим deadline worker. Cache хранит нормализованный индекс URL на 24 часа. Кандидат из sitemap сам по себе не подтверждает модель: `LGGlobalAdapter` должен прочитать PDP и вернуть `full_sku`. Проверки identity, readiness, документов и фото не ослаблялись. В реализации нет MS2082F URL или таблицы под 12 товаров.

Официальный внутренний search/API не исследовался далее: целевой PDP найден и прошёл validation через sitemap. Публичные Google/Bing/DDG остались последним fallback.

## MS2082F live gate

Обычный job `3bd8b697eaff4c649c49485e6b29ee5d` (стадии 1/2/3/4/6), перед ним backup `data/backups/stage54_4_before_ms.sqlite3`, production sitemap cache был пустым. KZ/RU вернули `mismatch`. Trace фиксирует путь:

`robots.txt` (200) → root index (80) → UK index (6) → UK `/uk/sitemap.xml` (10 463) → candidate `/uk/microwaves/solo/ms2082f/` → opened PDP → `full_sku`, `Main product sales code: data-pim-sku=MS2082F.CBKQEUK.EEUK.UK.C` → 69 характеристик, 36 фото → `external_search` skipped (`exact_official_sitemap_product_page_found`).

До job: 0 фактов, 0 фото, 0 документов, `not_ready`. После: 69 фактов, 36 фото, 0 документов, `export_ready_with_gaps`. Отсутствующая русская инструкция остаётся gap. Машинный trace: [ms_sitemap_trace.json](ms_sitemap_trace.json).

## Контроли

- P12ED.NSAR + P12ED.USAR: job `021f664629c44ab1ab288912829cedf0`, `needs_review`, 60,97 с. Точная PDP не подтверждена. UK/AU/CA sitemap просмотрены до бюджета без точного кандидата. Сохранены KZ support `full_sku`, связь NSAR↔USAR, русская инструкция, Sulpak candidate. Факты/фото 0/0; инструкция 1; readiness `not_ready`. Manual, характеристики и фото остаются отдельными типами доказательства.
- S40T: job из [controls_summary.json](controls_summary.json), `done`, 48,54 с. KZ и RU `full_sku`; оба provider skip с `exact_kz_ru_product_page_present`. Факты/фото 62/63, инструкция 1, `export_ready`. Sitemap и web search не вызываются.

Детали обоих запусков и источников: [controls_summary.json](controls_summary.json).

## Повторный прогон всей партии

12 обычных jobs со стадиями 1/2/3/4/6, backup `data/backups/stage54_4_before_batch.sqlite3`. Суммарное время 510,07 с. Во всех 12 readiness остался прежним. Сводка с official PDP, support, документами, фактами, фото, dealer candidates, конфликтами и временем по каждой строке: [batch_comparison.json](batch_comparison.json).

| ID | Модель | Статус | Факты | Фото | Инстр. | Конфликты | Время, с | Readiness |
|---:|---|---|---:|---:|---:|---:|---:|---|
| 4 | P12ED.NSAR + P12ED.USAR | needs_review | 0 | 0 | 1 | 0 | 58,00 | not_ready |
| 5 | S3WER.ALWPCOM | done | 56 | 59 | 0 | 0 | 64,45 | export_ready_with_gaps |
| 6 | MS2082F | done | 69 | 36 | 0 | 0 | 14,22 | export_ready_with_gaps |
| 7 | TW4V7EB1W | needs_review | 114 | 65 | 0 | 3 | 30,05 | export_ready_with_gaps |
| 8 | GC-B459MLWM.ADSQCIS | needs_review | 72 | 66 | 0 | 3 | 41,37 | export_ready_with_gaps |
| 9 | VK89309H | done | 47 | 63 | 0 | 0 | 47,24 | export_ready_with_gaps |
| 10 | W4W8LVPKZHM.APBPCOM | needs_review | 217 | 96 | 1 | 2 | 81,82 | export_ready_with_gaps |
| 11 | 86NANO81A6A | done | 140 | 78 | 1 | 0 | 31,30 | export_ready |
| 12 | RNC9.DRUSLLK | done | 130 | 80 | 1 | 0 | 38,19 | export_ready_with_gaps |
| 13 | S40T | done | 62 | 63 | 1 | 0 | 47,74 | export_ready |
| 14 | ON66 | done | 204 | 60 | 1 | 0 | 22,92 | export_ready |
| 15 | ON77DKDRUSLLK | done | 242 | 67 | 1 | 0 | 32,77 | export_ready_with_gaps |

В повторной партии новый sitemap candidate не понадобился: у MS2082F уже сохранена точная global PDP, у остальных точная KZ/RU PDP либо (P12ED) sitemap остаётся без кандидата. Единственное изменение уровня регионального источника: TW4V7EB1W RU `unknown` → `mismatch`; точная KZ PDP, число фактов/фото, конфликты и readiness не изменились.

## Проверки и Git

- Stage 54.4 offline: 17 тестов OK; Stage 54.1–54.4 targeted: 43 теста OK. `py_compile` новых модулей OK; отдельный offline coverage сценарий: 65 тестов OK.
- Full `python -m tests`: 1405 тестов OK за 806,065 с после исправления инициализации trace таблицы в offline coverage.
- `git diff --check`: OK. SQLite `integrity_check=ok`, `foreign_key_check=0` после 12 jobs.
- Commit/push и `HEAD == origin/main` выполняются после фиксации этого отчёта; фактический SHA и итог Git gate приведены в финальном ответе.

## Внешние зависимости

Для MS2082F и всех строк с сохранённой точной официальной PDP публичные поисковики не требуются. P12ED по-прежнему зависит от появления точной официальной товарной страницы или результативного внешнего поиска; русская инструкция и support не дают права считать specs/photos доказанными. У MS2082F отдельным gap остаётся русская инструкция.
