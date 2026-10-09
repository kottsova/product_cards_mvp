"""Rebuild Stage 68 audit from immutable inputs and recorded run results."""
import hashlib,json,re
from pathlib import Path
from bs4 import BeautifulSoup
from product_tool.xbox_identity import configuration_sensitive

R=Path(__file__).parent
def read(name):return json.loads((R/name).read_text(encoding='utf8'))
dataset=read('dataset.json');first=read('first_pass.json');live=read('final_live.json');final=read('acceptance_release_final.json');qa=read('qa_ui_excel.json')
sha=hashlib.sha256((R/'dataset.json').read_bytes()).hexdigest()
assert sha=='556dfe669181b1959e1d21dd52ed491f78719744bdbdab3442bef981de76191c'
assert len(dataset['rows'])==len(first['rows'])==len(final['rows'])==10
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in final['source_sha256'].items())
for row in final['rows']:
    ev=row['evidence'];exact=ev['configuration_complete']
    for fact in row['resolved']:
        if configuration_sensitive(fact['normalized_name']) and fact['selected_value']:
            assert exact and fact['selected_source']=='xbox_configuration',fact
    assert not ev.get('identifiers',{}).get('manufacturer_part_number')
white=final['rows'][3]
assert all('Carbon Black' not in s['description'] for s in white['sources'])
assert any('Robot White' in s['found_model'] and 'Robot White' in s['description'] for s in white['sources'])
groups=[]
for n in range(1,11):
    soup=BeautifulSoup((R/'ui'/f'product_{n}.html').read_text(encoding='utf8'),'html.parser')
    nodes=soup.select('.attribute-group');assert nodes
    assert all(x.get('data-role') in {'core','feature'} and x.get('data-section') for x in nodes)
    groups.append(dict(row=n,sections=[dict(role=x['data-role'],section=x['data-section']) for x in nodes]))
(R/'presentation_checks.json').write_text(json.dumps(dict(groups=groups,configuration_description_scope=True,source_hashes_current=True),ensure_ascii=False,indent=2),encoding='utf8')
reg=read('regression_release.json') if (R/'regression_release.json').exists() else None
passed=bool(reg and reg['exit_code']==0 and reg['source_tree_unchanged'] and 'OK' in reg['result'])
summary=read('acceptance_summary.json');summary.update(audit_verdict='PASS' if passed else 'Pending full regression',captured_final_file='acceptance_release_final.json',configuration_description_scope_verified=True,source_hashes_current=True,regression=reg and {k:v for k,v in reg.items() if k!='source_manifest'})
summary['artifact_tool']['final_shell_exit_code']=1
summary['artifact_tool']['note']='Five final previews written and independently decoded; renderer process failed after output. Earlier native exit -1073740791 retained; no renderer success claim.'
(R/'acceptance_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')
def table(headers,rows):return '\n'.join(['| '+' | '.join(headers)+' |','|'+'|'.join(['---']*len(headers))+'|',*['| '+' | '.join(str(v).replace('|','\\|').replace('\n',' ') for v in row)+' |' for row in rows]])
def selected(r):return sum(bool(p['selected']) for p in r['photos'])
def link(u,label):return f'[{label}]({u})' if u else 'не подтверждён'
def family_url(r):return next((s['url'] for s in r['sources'] if s['source_key']=='xbox_model' and s['url']),'')
frozen=table(['№','Вход / identifier type','Модель — только query hint','Регион'],[(r['row'],r['article']+' / '+r['identifier_type'],r['name'],r['requested_region']) for r in dataset['rows']])
firsttable=table(['№','Official PDP','Support','Model / configuration identity','Raw / facts / confirmed specs','Фото','Manual','Dealer','Job / readiness','Главный gap'],[(r['input']['row_number'],link(family_url(r),'семейство'),link(r['evidence'].get('support_url',''),'индекс'),r['evidence']['identity']['model']+' / '+r['evidence']['identity']['configuration'],f"{len(r['evidence']['raw_specs'])} / {len(r['facts'])} / {r['readiness']['confirmed_specs']}",selected(r),r['evidence']['manual_status'],r['evidence'].get('dealer_fallback',{}).get('status','не запускался'),r['job']['status']+' / '+r['readiness']['verdict'],', '.join(r['readiness']['blocking_gaps'])) for r in first['rows']])
finaltable=table(['№','Exact PDP / family','Configuration identity','Hardware identity','Confirmed specs','Фото','Live / captured readiness','Remaining blockers'],[(r['input']['row_number'],link(r['evidence'].get('exact_official_pdp') or family_url(r),'Store' if r['evidence'].get('exact_official_pdp') else 'семейство'),r['evidence']['identity']['configuration'],r['evidence']['identity']['hardware'],r['readiness']['confirmed_specs'],selected(r),live['rows'][i]['readiness']['verdict']+' / '+r['readiness']['verdict'],', '.join(r['readiness']['blocking_gaps']) or 'нет; manual — advisory') for i,r in enumerate(final['rows'])])
regtext='Ожидается завершение полного прогона; PASS ещё не объявлен.' if not passed else f"`{reg['command']}`: **{'; '.join(reg['result'])}**, exit **0**, {reg['elapsed_seconds']:.1f} с. SHA-256 всех application/test `.py`, `.js`, `.html` до и после совпадают: `source_tree_unchanged=true`."
text=f'''# Stage 68 — Xbox baseline audit и перенос общего pipeline

Audit: **{'PASS' if passed else 'PENDING'}**. Brand verdict: **Xbox adapter not ready**.
Набор неизменен; обычный первый запуск 0/10 ready, последний сохранённый live 2/10, окончательная проверка на захваченных публичных ответах 6/10. Captured transport проверяет extraction/identity/integration, но не доказывает live discovery success. Ложных подтверждённых configuration facts в окончательном прогоне нет; отрицательные контроли проверяют также название и описание выбранного цвета.

## 1. Baseline

Исходный HEAD `aba854121464779dccf909d817d50d315a31018e`. До адаптации обычный `run_once()` получил артикул **1882**, commercial name **Xbox Series X**, brand Xbox, category consoles. Ссылка Learn была исследовательским обоснованием входа и не передавалась worker. Region audit en-US; retail SKU/part, color, storage не известны.
Job **error**, readiness **not_ready**; official PDP, support/manual, facts и photos отсутствуют. Общая ветка использовала только DNS и получила `dealer_url_needed`, без проверенного URL. Query variants `1882`, `Xbox Series X 1882`, `Xbox Series X` зафиксированы, но Xbox official discovery в исходном worker отсутствовал; отдельная discovery trace пуста, фактическое исполнение полностью видно в семи job events. Не приписываем выполненные запросы предложенным вариантам. Worker SHA совпал до/после baseline. [Полный baseline](baseline.json), [скрипт](baseline.py).

## 2. Official Xbox / Microsoft structure

| Источник | Что действительно публикует | Граница доказательства |
|---|---|---|
| [Xbox Series X](https://www.xbox.com/en-US/consoles/xbox-series-x), [Series S](https://www.xbox.com/en-US/consoles/xbox-series-s) | Bounded specs drawer: PROCESSOR, MEMORY & STORAGE, VIDEO, SOUND, PORTS, DESIGN; варианты накопителя/привода/веса | Семейство и общие specs; таблица с несколькими вариантами не выбирает SKU |
| Xbox accessory PDP / technical tables | Battery, connectivity, controls, haptics, compatibility и варианты массы/комплектации | Не доказывает текущую hardware revision по одному имени |
| Declared `allConsoles.js`, `allAccessories-Sheet1.js` | Locale rows, `detailsURL`, `poPid`, `gaPid`, `specPid` | Catalog IDs — кандидаты для discovery; это не manufacturer part number |
| Xbox robots → CMS sitemap; Microsoft robots → Store sitemap index → hardware maps | Product links; региональные `xhtml:link` alternates; gzip | Реальный опубликованный маршрут; Unicode XML не декодируется как binary PDF |
| [Store controller](https://www.microsoft.com/en-us/d/xbox-wireless-controller/8xn59crbsqgz) | JSON-LD Product ID и `window.__BuyBox__.product.skuInfo`: SKU/title/display/gallery | Own row нужен для SKU; H1 и даже SKU gallery могут содержать другой default color |
| [Xbox Support manuals](https://support.xbox.com/en-US/help/hardware-network/console/manuals-specs) | SPA shell → declared public GET content API → ContentList/SectionItems → family PDF links | HTTP 200 shell не является проверенной инструкцией |
| [Learn Series X device ID](https://learn.microsoft.com/en-us/xbox/service-guides/series-x-console/series-x-device-id-and-disassembly), [Series S device ID](https://learn.microsoft.com/en-us/xbox/service-guides/series-s-console/series-s-device-id-and-disassembly) | Explicit Models 1882 / 1883; service document and spare-part IDs | Hardware number отдельно; service document part и replacement part не являются retail SKU |

Public Support GET строится только после проверки endpoint/method/path/query declaration в bundle: `https://content.support.xboxlive.com/content?path=/SXC/hardware-network/console/manuals-specs&language=ru-RU&market=RU`. Это опубликованный anonymous content contract. JSON assignments читаются `JSONDecoder.raw_decode`, JavaScript не исполняется. Источники и исходные ответы: [survey log](explore_http.json), `observed/`, [runtime HTTP](xbox_fetch.json), `xbox_captures/`.

Discovery: regional family → declared official sitemap/catalog → own Store pages → Support/device ID → other official regions → existing LG browser/search contracts → existing DNS fallback. Five family route hints служат стартовыми страницами; каждое собственное H1 проверяется. Нет registry десяти SKU→URL, нового search engine или hardware framework. Store ссылки берутся из опубликованных страниц и sitemap; регион и exact ID проверяются после ответа. Query/provider/URL/region/type/accepted/reason/relation сохраняются в per-job trace. Shared Bing/Google browser не дал надёжных PDP кандидатов в этих live runs; access/policy stops сохранены в [search log](xbox_search.json). Dealer evidence отдельно, неподтверждённый URL не становится official fact.

## 3. Identity rules

Family, commercial configuration, Store Product ID, Store SKU ID, manufacturer part number, hardware model number, region и revision различаются. Четырёхзначный вход типизируется как hardware number, но подтверждается только собственным источником; типизация не является evidence. `8XN59CRBSQGZ/KPRJ` означает Product ID плюс SKU, а не manufacturer part.
Exact Store identity требует своего URL/Product ID, own payload/JSON-LD и совпавшего storefront. При нескольких `skuInfo` Product ID один не выбирает default color; нужен собственный SKU/title. Catalog старый White `LK4W` не принимается за текущий `KPRJ`. Название строки Excel остаётся query hint. `manufacturer_part_number` не изобретён ни для одной строки. Model facts допускаются без retail SKU; storage/color/disc/kit/weight/axes не допускаются из model-only источника. Для запроса `1883` опубликованная hardware identity не подтверждает retail конфигурацию и физическую ревизию.

Default H1 Store Carbon Black сохранён как `page_default_titles` evidence; белая SKU row задаёт Robot White в `found_model` и description. У model-only документа название ограничено семейством. Проверены оба цвета и Product ID без SKU.

## 4. Storage / configuration / physical values

До canonical mapping сохраняется `section → raw label → value`. Advertised storage, usable storage, expansion-card support и USB external storage — отдельные поля. Own S 1 TB Store даёт `1TB Custom NVME SSD`; own Starter bundle — `512GB Custom NVME SSD`. Ни 512 GB из query hint, ни список 512 GB / 1 TB / 2 TB не становится exact storage. Usable capacity не опубликована в подтверждённых источниках и не вычисляется.
Disc/Digital и цвета из общей многовариантной таблицы остаются candidates. Масса/габариты без собственных variant/revision, явных осей и assembly binding удерживаются. Store S 1 TB даже публикует необычный общий dimensional triple — он не превращается в axis facts. Elite `345g ±15g` со сборкой не становится bare controller weight. Headset own SKU публикует 320 g, отображение — 0.32 кг. Common axis keys и cm→mm/g→kg проверены отдельно; синтетический metric control не выдаётся за найденные физические размеры frozen consoles.
CPU/GPU architecture — model-level. Для hardware-number запроса частоты CPU/GPU, runtime и radio revision удерживаются без exact revision linkage. Store и family могут публиковать разные clock values; own exact Store факты имеют scoped priority, исходные альтернативы остаются видимыми.

## 5. Bundles, photos, manuals, descriptions

[Diablo IV bundle](https://www.microsoft.com/en-us/d/xbox-series-x-diablo-iv-bundle/8n1bb8dsbknt) реально существует и доступен в исследовательском capture. Его own includes подтверждает Diablo IV и бонусные игровые предметы; Game Pass продаётся отдельно. Own parsing проверен тестом, но ordinary discovery не нашёл этот отсутствующий в актуальных catalog links товар — frozen row 8 остаётся not_ready. Это discovery gap, а не отсутствие PDP.
[Starter bundle](https://www.microsoft.com/en-us/d/xbox-series-s-starter-bundle/8zb8z8mm10v0) подтверждает собственные 512 GB и 3 months Game Pass Ultimate. Second controller, packaging contents или цвет не выводятся из базового комплекта/названия/картинки. Обе bundle rows независимы; base console не получает их game/kit.

Каждое gallery asset отдельно проверяется на family/color, даже если gallery находится в собственной SKU row. Black QP6M не становится фото White KPRJ; special Arctic Camo подтверждается своим ZHP2. Other color/bundle/lifestyle assets остаются photo candidates. Exact storage не требует отдельного рендера при явно связанном own Store asset; generic family exterior без связи не становится exact. Семь реальных official JPEG полностью декодированы, измерены и визуально просмотрены: S 1 TB 1, White controller 1, Arctic 1, Elite 2, headset 1, Starter 1. У Starter фактическое изображение — коробка bundle, несмотря на generic Series S alt; оно принадлежит own Store row, не используется для вывода комплекта или для base-console фото. Metadata: [photo inspection](photo_inspection.json), [contact sheet](photo_contact.png), [independent decode](image_validation.json).

User Guide / Setup Guide / Safety-Regulatory / Support article — отдельные роли. Три PDF реально проверены на bytes/структуру и отрисованы: console RU 16 pages, accessory multilingual 132, Elite multilingual 88. Обложки — product/regulatory/warranty, не User Guide. В RU PDF ToUnicode повреждает извлечение кириллицы и в pypdf, и в PDFium: визуально русский текст есть, runtime language verification недостаточна. Поэтому все десять User Guide statuses **«Не проверена»**, а не «Проверена, не найдена». Optional manual — advisory, не блокирует ready. [PDF render evidence](document_render.json), [RU cover](cab906c49b3dbd25fd6b_page_1.png). Статусы «Проверена» и «Проверена, не найдена» предусмотрены лишь для реально проверенного User Guide / полного проверенного поиска соответственно.
Descriptions строятся из scoped product title и допущенных характеристик. Account setup, activation, reset, repair, warranty и firmware procedures не используются; raw support/source candidates остаются доказательствами, а не описанием.

## 6. Frozen ten inputs

Frozen **{dataset['frozen_at']}**, перед первым adapted run **{first['started']}**. SHA-256 **`{sha}`**. Baseline 1882 не повторяется как отдельная frozen row; frozen сложный hardware case — 1883 / GB. Имена могут содержать желаемые опции, но не подтверждают их. Входы не менялись после первого запуска. [Dataset](dataset.json), [digest](dataset.sha256).

{frozen}

## 7. First-pass and final results

Первый adapted pass — обычный worker, без transport/adapter factory, без PDP URL во входах. Все десять family identities подтверждены, exact configurations не подтверждены, selected photos 0; все jobs needs_review, readiness not_ready. Колонки Raw/facts/confirmed различают исходные строки, нормализованные facts и подтверждённые технические поля. [First-pass JSON](first_pass.json).

{firsttable}

Последний сохранённый live run готовит строки 4 и 6: **2/10**. Network timeouts / budget / blocked search и ещё не исправленные на тот момент extraction guards сохранены честно. Окончательные sources проверены transport-only replay на собственных захваченных публичных ответах; factories заменяют HTTP/search transport, не discovery registry. Captured readiness **6/10**, это не новая live гарантия. Все десять model identities сохранены. [Final live](final_live.json), [final captured acceptance](acceptance_release_final.json).

{finaltable}

Ранние промежуточные `validation_live`, `acceptance_replay`, `acceptance_final`, `acceptance_release` не переписывались. Они показывают развитие исправлений и не являются окончательной приёмкой. Окончательная production SHA manifest в `acceptance_release_final.json` совпадает с текущими файлами.

## 8. Six edge cases and UI / Excel

| Edge | Результат отрицательного контроля |
|---|---|
| Series X vs S | Own H1 family mismatch отклоняется, атрибуты не принимаются |
| 512 GB vs 1 TB | Own Starter 512 GB / own S 1 TB независимы; options и usable storage не изобретаются |
| Same controller, different color | KPRJ Robot White / QP6M Carbon Black: независимые photos, title и description; чужой цвет candidate |
| Base vs bundle | Diablo game / Starter Game Pass из own evidence; base не получает bundle kit, second controller или packaging |
| Regional SKU | en-US ответ не подтверждает en-GB SKU; stale catalog LK4W не равен own KPRJ |
| Revision values | Model 1883 подтверждён Learn, но weight/axes/clocks/runtime/radio другой ревизии удерживаются |

Штатный FastAPI UI: **10 HTTP 200**; проверены русские labels, existing parent sections и roles core/feature, отдельные identity/configuration/storage/bundle/candidate/manual blocks. Сейчас admitted Xbox rows проходят как core; отсутствующие feature specs не создавались ради заполнения. Имена фирменных технологий сохраняют регистр, hours отображаются как ч, общая metric projection использует mm/kg. Support procedures отсутствуют в descriptions. Скриншоты overview/evidence строк 3,4,7,9,10 и White photo lightbox сохранены. [UI/Excel QA](qa_ui_excel.json), [presentation controls](presentation_checks.json), [White UI](ui_4_evidence.png), [lightbox](ui_4_lightbox.png).
Native openpyxl export валиден, ten readiness rows, ошибок ячеек/формул нет. Дополнительные sheets: «Готовность Xbox», «Конфигурация Xbox», «Идентификаторы Xbox», «Кандидаты Xbox», «Документы Xbox», общий «Фото-кандидаты». Исходные labels/sections сохранены в candidates. [Excel](export.xlsx), [readiness preview](excel_readiness.png), [configuration preview](excel_configuration.png). ArtifactTool read-only import/render записал все пять final previews; независимый PNG decode проходит. Его процесс завершился ошибкой после вывода (final shell exit 1, предыдущий native exit -1073740791). Это ограничение renderer runtime; успех процесса renderer не заявляется, native exporter проверен отдельно.

## 9. Нужен ли отдельный hardware-resolution layer

**В этом Stage отдельный framework не требуется.** Brand adapter уложился в существующие policy HTTP, shared sitemap/search/dealer, jobs/storage, normalization/resolution, evidence/readiness, UI/export. Существующие brand thresholds сохранены; добавлены отдельные Xbox source scopes и короткие typed identity guards.
Открытая задача — доказанная связь hardware model/revision ↔ retail SKU/manufacturer part и exact discovery по commercial configuration. Это расширение evidence/resolution contracts, не доказательство необходимости нового framework. Набора из десяти недостаточно, чтобы объявить весь Xbox production-ready.

## 10. Regression and integrity

{regtext}
[Regression summary](regression_release.json). Targeted Xbox: **26 tests OK**; neighboring Stage 66/67 PlayStation: **41 tests OK**. Полный набор ожидает 1584 прежних + 26 новых tests. Два ранних полных прогона остановлены для реальных найденных исправлений; они не засчитываются. В финальном полном прогоне application/test sources не меняются.
Archive source protection: только новый Stage 68 authorization/pins block в `tests/_pipeline_migration.py`, все предыдущие pins/reports сохранены. Ten changed shared production files имеют финальные SHA pins; новые Xbox files входят в regression source manifest. [Migration evidence](migration_record.json). `.gitattributes` задаёт `-text` для Stage 68 evidence, чтобы Windows autocrlf не менял frozen/captured bytes. Перед commit обязательны `git diff --check`, staged dataset SHA verification и full regression PASS.

## 11. Verdict and concrete blockers

Audit **{'PASS' if passed else 'PENDING'}**; **Xbox adapter not ready**.

Исправленные системные ошибки: Unicode sitemap ошибочно прошёл binary document conversion; gzip bytes терялись; региональные sitemap URLs были в alternates; несколько audio formats стали ложным конфликтом; photo `box` regex совпадал с Xbox; собственный published image CDN исключался; default Black title ошибочно описывал White SKU; normalization меняла регистр branded terms. Исправления проверены реальными captures и отрицательными контролями.
Остаются реальные/не закрытые gaps:

- Rows 1/2: commercial name не подтверждает exact retail storage/color/disc; нужны own configuration relations и exact photos.
- Row 8: исследованный Diablo PDP существует, но обычная discovery chain его не нашла через текущие опубликованные catalog/sitemap links и blocked browser fallback.
- Row 10: published 1883 не связывает hardware revision с конкретным GB retail SKU/physical table; перенос массы/габаритов запрещён.
- Live discovery нестабилен: captured 6/10 нельзя выдавать за live 6/10.
- Canonical extraction coverage неполна: некоторые SoC/process/control fields и многовариантные physical values остаются candidates; не все platform features извлечены.
- RU PDF text/language verification остаётся незавершённой; manual optional, поэтому это advisory, но статус не повышен.

## 12. Git delivery

После full PASS: commit **`Stage 68`**, push main, проверка `HEAD == origin/main` и clean working tree. Сам hash сообщается после commit в финальном ответе, чтобы не создавать self-referential report commit. Предыдущие Stage 66/67 evidence не переписаны.

Воспроизведение (из repository root, `PYTHONPATH=.`):

```powershell
.venv\\Scripts\\python.exe -m tests test_xbox_stage68.py
.venv\\Scripts\\python.exe reports/xbox_stage68/replay.py acceptance_new
.venv\\Scripts\\python.exe reports/xbox_stage68/run_regression.py
```

Replay требует нового имени фазы и не перезаписывает предыдущую DB. Final QA использует `acceptance_release_final.sqlite3`; reproducible capture scripts и все PDF/HTML/JSON inputs архивированы, SQLite не коммитится. `build_report.py` сверяет final source hashes, configuration scope, descriptions, UI groups и только после успешной полной регрессии выставляет audit PASS.
'''
(R/'REPORT.md').write_text(text,encoding='utf8')
print('Report rebuilt:',summary['audit_verdict'],flush=True)
