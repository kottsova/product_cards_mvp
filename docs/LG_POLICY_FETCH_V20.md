# LG: policy-aware fetch и пилот (Stage 20)

Отчёт этапа — `reports/source_census_2026-09-24_stage20/report.md`.

## Что изменилось в сетевом слое LG

`LGAdapter`, `LGRUAdapter` и `SulpakAdapter` (защищённые файлы `adapters/lg.py`, `adapters/sulpak.py`) не менялись: они по-прежнему вызывают `fetch_with_retry(session, url, …)`. Меняется сессия, которую им передаёт worker по умолчанию:

* `adapters/policy_session.PolicyAwareSession` — объект в форме `requests.Session` (`get`, `headers`) поверх `PolicyAwareFetcher`. Каждый запрос идёт через список разрешённых host, проверку цепочки редиректов, определение 401/403/429 и подтверждённого challenge, и записывается в постоянный журнал.
* `adapters/lg_policy.default_lg_adapters(directory)` строит тройку адаптеров; журнал — `<каталог данных>/lg_fetch_log.json` (для рабочей БД `data/lg_fetch_log.json`, он же источник остановок для планировщика). Host: `lg.com` (LG Казахстан, LG Россия) и `sulpak.kz`.
* `worker.run_once()` без внедрённых адаптеров использует `default_lg_adapters(database.parent, clock=clock)` (запись в `tests/_pipeline_migration.py`, закрепление хэша обновлено).

Правила:

| Ситуация | Поведение |
|---|---|
| 401/403/429 в журнале, новый экземпляр или следующий запуск | host остановлен, запрос не делается, ответ помечен `[policy_host_stopped]` |
| подтверждённый challenge при HTTP 200 (`challenge_confirmed` / `browser_verification_required`) | страница адаптеру не отдаётся (`[policy_challenge_confirmed]`), host остановлен и в следующем запуске |
| `challenge_suspected` | записывается, ничего не останавливает, страница отдаётся адаптеру как раньше |
| host вне списка | запрос не делается (`[policy_host_not_allowed]`) |
| бюджет (на строку / всего) | запрос отклоняется до отправки (`[policy_budget_exhausted]`); кэш и отказ запросом не считаются |
| sitemap | ответ кэшируется в процессе на 10 минут по ключу (журнал, URL): пакет строк читает sitemap один раз |
| заголовки | User-Agent и Accept-Language адаптера сохраняются (`headers` — словарь нижележащей сессии) |

Что не менялось: что LG-адаптеры ищут, разбирают и извлекают, включая повторную попытку на 5xx (`fetch_with_retry`). DNS-адаптер сетевой слой не менял (он ходит только по заранее проверенным URL).

`PolicyAwareSession` также умеет писать все ответы в каталог (`record_responses`) — так сохранены страницы и sitemap пилота для офлайн-диагностики.
