"""Consolidate immutable first-pass data and source-grounded release evidence."""
import hashlib,json,re
from pathlib import Path
from bs4 import BeautifulSoup
from product_tool.playstation_pipeline import GAPS
from .probe_sources import URLS
r=Path('reports/playstation_stage66')
def read(name):return json.loads((r/name).read_text(encoding='utf-8'))
baseline=read('baseline.json')['results'][0];first=read('first_pass.json');release=read('release_replay_verified.json');qa=read('qa_ui_excel.json');digest=hashlib.sha256((r/'dataset_frozen.json').read_bytes()).hexdigest()
assert first['dataset_sha256']==release['dataset_sha256']==digest
assert len(first['results'])==len(release['results'])==10
assert all(x['readiness']['verdict']=='not_ready' for x in release['results'])
assert not any(f['conflict'] for x in release['results'] for f in x['resolved'])
assert all(not s['description'] for x in release['results'] for s in x['sources'])
order_claims=[dict(article=x['input']['search_code'],name=f['normalized_name'],value=f['selected_value'],source=f['selected_source']) for x in release['results'] for f in x['resolved'] if f['full_sku_confirmed']]
assert {x['article'] for x in order_claims}=={'1000050213-GB'}
assert {x['name'] for x in order_claims}=={'color','комплектация'}
assert sum(p['selected'] for x in release['results'] for p in x['photos'])==2
structure=[]
logs=read('probe_http.json')
for key,url in URLS.items():
    p=r/(key+'.html')
    if not p.exists():continue
    body=p.read_text(encoding='utf-8');s=BeautifulSoup(body,'html.parser');entry=next((x for x in reversed(logs) if x.get('url')==url),{})
    ld=[]
    for tag in s.select('script[type="application/ld+json"]'):
        try:
            value=json.loads(tag.get_text());values=value if isinstance(value,list) else [value]
            ld.extend({k:x.get(k) for k in ('@type','name','sku','mpn','productID') if k in x} for x in values if isinstance(x,dict))
        except (ValueError,TypeError):pass
    structure.append(dict(key=key,url=url,final_url=entry.get('final_url') or url,status=entry.get('status_code'),captured_body_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),h1=[h.get_text(' ',strip=True) for h in s.select('h1')],json_ld=ld,order_sku=re.findall(r'\bsku\s*:\s*"([^"]+)"',body),sitemap_locs=re.findall(r'<loc>([^<]+)</loc>',body),cfi_label_count=sum('CFI-' in a.get_text() for a in s.select('a[href]')),public_embedded_api_attributes=[dict(attribute=k,value=v) for tag in s.select('[aemendpoints]') for k,v in tag.attrs.items() if k=='aemendpoints']))
(r/'source_structure.json').write_text(json.dumps(structure,ensure_ascii=False,indent=2),encoding='utf-8')
regression=read('regression_release.json') if (r/'regression_release.json').exists() else None
passed=bool(regression and regression['exit_code']==0 and regression['source_tree_unchanged'])
matrix=[]
for x in release['results']:
    ev=x['evidence'];ready=x['readiness'];sources=[dict(key=s['source_key'],url=s['url'],relation=s['match_level'],error=s['error']) for s in x['sources']]
    matrix.append(dict(article=x['input']['search_code'],name=x['input']['name'],model_identity=ev['identity']['model'],configuration_identity=ev['identity']['configuration'],hardware_model=ev.get('hardware_model',''),hardware_family=ev.get('hardware_family',''),exact_official_pdp=ev.get('exact_official_pdp',''),support=ev.get('support_url',''),sources=sources,raw_specs=len(ev['raw_specs']),facts=len(x['facts']),confirmed_specs=ready['confirmed_specs'],photo_candidates=len(ev['photo_candidates']),selected_photos=sum(p['selected'] for p in x['photos']),manuals=ev['manuals'],manual_status=ev['manual_status'],dealer=ev.get('dealer_fallback',{}),job_status=x['job']['status'],readiness=ready['verdict'],blocking_gaps=ready['blocking_gaps'],configuration_fields=ev['configuration_fields']))
summary=dict(stage=66,baseline_article='CFI-2016A',baseline_job=baseline['job']['status'],baseline_facts=len(baseline['facts']),first_pass_rows=10,dataset_sha256=digest,final_rows=10,export_ready=0,confirmed_configuration_claims=order_claims,false_confirmed_configuration_claims=0,real_conflicts=0,selected_exact_photos=2,user_guides_verified=sum(x['manual_status']=='Проверена' for x in matrix),adapter_verdict='PlayStation adapter not ready',stage_acceptance='PASS' if passed else 'PENDING_REGRESSION',hardware_resolution_layer='Not justified; scoped CFI table routing fits the shared evidence contracts',regression=regression,matrix=matrix)
(r/'acceptance_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
table='\n'.join(f"| {x['article']} | {x['hardware_family'] or 'модель PDP'} | {x['configuration_identity']} | {x['confirmed_specs']} | {x['selected_photos']} | {x['manual_status']} | {', '.join(x['blocking_gaps'])} |" for x in matrix)
report=f'''# Stage 66 PlayStation baseline и перенос общего pipeline

Дата: 2026-10-08 (Asia/Tbilisi). Исходный commit: `d103864609a6809be7bd91e2b0b1cdc2ac047b1b`.

Вердикт: **PlayStation adapter not ready**. Stage 66 acceptance: **{'PASS — baseline, независимая выборка, разделение identity, отрицательные контроли и полный regression' if passed else 'PENDING — полный regression ещё не завершён'}**. Это аудит переносимости и безопасная интеграция; производственную готовность бренда не объявляем. Все 10 карточек остаются `needs_review / not_ready`. Для Midnight Black доказаны SKU, цвет, комплект и два собственных рендера, но технических характеристик пока недостаточно. Цвет и комплектация не заполняют счётчик specs readiness.

## 1 Baseline

Обычный неизменённый `run_once()` Stage 65 для **CFI-2016A**, входное имя PlayStation 5 Slim Disc 1TB CFI-2016A: job `error`, 0 specs, 0 фото, 0 документов, readiness `not_ready`. Commercial name и Disc/1TB/Slim во входе были только hints; hardware identity, retail SKU, revision и точный PDP не были подтверждены. Официального PlayStation dispatch не существовало. Общий DNS fallback вернул `dealer_url_needed`, а не выдуманную URL-карточку. Официальный поиск и query variants в этой ветке не выполнялись: это systemic dispatch gap, а не доказанное отсутствие товара. `baseline.json` сохраняет input, job, source, факты, решения, photos, documents, readiness и events.

Контрольный повтор после интеграции сохранён отдельно в `baseline_final.json`: официальный CFI/support связан, объединённая таблица Slim остаётся кандидатом. Исходный baseline не перезаписан.

## 2 Официальная структура

- [PlayStation UK PS5](https://www.playstation.com/en-gb/ps5/) и [PS5 Pro](https://www.playstation.com/en-gb/ps5/ps5-pro/) — коммерческие family/model страницы на AEM. Текущая PS5 family page не является exact PDP старой CFI-1216A/B и не подтверждает параметры любой ревизии.
- [DualSense](https://www.playstation.com/en-gb/accessories/dualsense-wireless-controller/), [Portal](https://www.playstation.com/en-gb/accessories/playstation-portal-remote-player/) и [PULSE Elite](https://www.playstation.com/en-gb/accessories/pulse-elite-wireless-headset/) — модельные возможности, галереи и варианты. PULSE Elite JSON-LD Product содержит `mpn=CFI-ZWH2EC`; CMS `sku/productID=PSD001...` не объявлены retail SKU. Другие исследованные страницы часто дают BreadcrumbList/VideoObject вместо exact Product record.
- [RU manuals](https://www.playstation.com/ru-ru/support/hardware/manuals/) и [UK manuals](https://www.playstation.com/en-gb/support/hardware/manuals/) — CFI labels и реальные href для User Guide, Quick Start и Safety Guide. Встречаются combined A/B tables и отдельные accessory/component guides. Сходный prefix не связывает CFI-ZWH2 с CFI-ZWH2EC автоматически.
- [Direct Midnight Black PDP](https://direct.playstation.com/en-gb/buy-accessories/dualsense-wireless-controller-midnight-black-for-ps5-pc-mac-mobile) публикует `digitalData.product[0].productInfo.sku=1000050213-GB`. Own h1, SKU, own box list и image-cluster — отдельные доказательства. Опции другого SKU, включая USB Cable bundle, в confirmed gallery не входят.
- [Direct Fortnite PDP](https://direct.playstation.com/en-gb/buy-consoles/playstation5-digital-edition-console-825-gb-fortnite-flowering-chaos-bundle) публикует `1000049849-GB`, 825 GB и собственный Fortnite voucher/box list. Страница реально существует; текущий adapter discovery её не находит самостоятельно. Известный research URL не был внедрён в production SKU registry.
- [robots.txt](https://www.playstation.com/robots.txt) объявляет [sitemap index](https://www.playstation.com/sitemap_index.xml), а не root `/sitemap.xml` (404). Index содержит региональные sitemap, включая RU и GB. `sitemap_gpdc.xml` имеет отдельный robots запрет; это не запрет всех региональных карт. Adapter пока сохраняет index diagnostics, но не обходит региональные children — конкретный discovery blocker.
- Legacy `support.playstation.com` и SIE corporate pages исследованы как support/corporate surfaces; они не заменяют exact PDP. Наблюдённые embedded AEM endpoints Direct относятся к cart/session/checkout; как публичный specs API они не использованы. Полный runtime XHR trace не заявлен.

Наблюдения, returned URL/status, captured-body hashes, JSON-LD, embedded SKU и sitemap locs сохранены в `source_structure.json`. HTTP logs и captures относятся к текущему Stage 66. Capture hash для HTML относится к сохранённому decoded body; PDF hashes относятся к исходным binary bytes.

## 3 Identity и evidence

`playstation_model` — доказанная модель/family PDP, только model-stable facts. `playstation_hardware` — exact official CFI и cover-checked technical guide; status `hardware_confirmed_official`, **не** `full_sku_confirmed`. `playstation` — retail order SKU из собственного Direct PDP, status `full_sku_official` только для exact order facts.

Официальный CFI сохраняется типом `official_hardware_model_code`. Числовой regional suffix сам по себе не подтверждает radio, disc-region или retail bundle. `storefront=en-gb` означает регион магазина. Hardware family/revision выводится из наблюдённой структуры официального guide, а не из имени входной строки. CFI-2016A/B разворачивается в два отдельных identifier; CFI-2015A, другой chassis и suffix EC не подменяются похожими кодами.

Storage/color/bundle/Disc-Digital/region/revision/dimensions/weight не подтверждаются family options. Raw section → label → value сохраняется до mapping, неизвестные технические строки и условные опции остаются candidates. Общие возможности DualSense сохраняют брендированные Haptic Feedback / Adaptive Triggers, а текст рекламы не сравнивается как несколько конфликтующих numeric specs. Отрицательные feature statements не становятся «Да».

## 4 CFI, ревизии и габариты

На реально скачанных и отрендеренных страницах Safety Guide:

| Hardware | Размеры Ш × В × Г | Масса | Scope |
|---|---|---|---|
| CFI-1216A | 390 × 104 × 260 мм | около 3,9 кг | original Disc, без выступающих частей |
| CFI-1216B | 390 × 92 × 260 мм | около 3,4 кг | original Digital, без выступающих частей |
| CFI-2016 с disc drive | 358 × 96 × 216 мм | около 3,2 кг | строка объединённой Slim таблицы, candidate |
| CFI-2016 без disc drive | 358 × 80 × 216 мм | около 2,6 кг | другая строка Slim таблицы, candidate |
| CFI-7021 | 388 × 89 × 216 мм | около 3,1 кг | Pro guide; значения без добавленного disc drive |

Original 1200a/1200b технические таблицы, Slim combined table и Pro table визуально проверены. Slim dimensions/weight не повышаются до confirmed до row-level Disc/Digital routing. Console specs обрываются перед отдельной Wireless controller/DualSense таблицей: масса 280 г и controller battery не относятся к консоли. Package / with-stand размеры отдельный отрицательный контроль. UI/Excel: Ширина, Высота, Глубина, Вес; русские units, CFI scope отдельно от retail confidence.

## 5 Bundles и фотографии

Fortnite PDP parser принимает комплектацию только при собственном `1000049849-GB`. Для CFI-2016A та же страница не подтверждает SKU/storage/box contents. Bare console и bundle не эквивалентны по комплекту. Unit-test probe этого PDP не означает discovery success для frozen SKU: это остаётся blocker.

Midnight Black own box list: DualSense Wireless Controller; User manual. Slogan соседнего блока исключён. USB Cable bundle selector — фото-кандидат другого комплекта. Только два собственных image-cluster renders подтверждены для exact black order/color. Оба реально скачаны и визуально проверены: 400 × 400 JPG, {read('photo_inspection.json')[0]['size_bytes']} и {read('photo_inspection.json')[1]['size_bytes']} bytes. У других вариантов/ревизий нет автоматически выбранных подтверждённых фото. Gallery и lightbox проверены с измеренными metadata.

## 6 Frozen dataset и первый прогон

`dataset_frozen.json`, SHA-256 `{digest}`. Десять новых identifier после отдельного baseline; выбор не менялся после результатов. CFI hardware identifier и retail SKU явно различаются; White/storage/bundle слова входного имени не считаются доказательствами.

Все 10 первых неизменённых запусков получили `error / not_ready`, 0 specs/фото/manuals, общий dealer URL gap. `first_pass.json` сохранён. Последующий живой `final_live.json` прогнал те же 10 строк без model-specific SKU→URL registry. Финальный `release_replay_verified.json` — offline `run_once()` на реальных сохранённых HTTP/PDF bodies после safety fixes; это parser/evidence replay, не отдельный свежий сетевой успех.

| Identifier | Доказанная модель/guide family | Configuration identity | Technical specs¹ | Exact фото | RU User Guide | Главный gap |
|---|---|---|---:|---:|---|---|
{table}

¹ Счётчик readiness исключает цвет, комплектацию и storefront metadata. Сырых facts: {sum(x['facts'] for x in matrix)}; до canonical mapping сохранено {sum(x['raw_specs'] for x in matrix)} raw records. Во всех 10 итоговых строках job `needs_review`, readiness `not_ready`; реальные conflicts 0. `acceptance_summary.json` содержит по каждой строке exact PDP, support, sources, обе identity, hardware family, конфигурацию, facts, photos, guides, dealer и gaps.

## 7 Инструкции, support и dealer

Русский User Guide подтверждён actual complete PDF bytes, cover CFI и русским instruction content для CFI-ZCT1W и CFI-Y1016: «Проверена». Safety/QSG/Regulatory и support article отдельные роли; Safety не объявлен User Guide. Остальные: «Не проверена», поскольку полная exact-generation проверка не завершена. «Проверена, не найдена» после неполной проверки не ставится. Manual advisory и сам по себе не блокирует readiness.

PSN/account setup, repair/reset/update/warranty не включены в product description. Description для этих audit карточек пустое; это ограничение текущего extraction, а не подтверждённое описание товара. Общий DNS dealer fallback работает, возвращает `dealer_url_needed` без зарегистрированной exact URL. Dealer evidence хранится отдельно и не подтверждает official facts. Точные retailer bundle/packaging URL не найдены внутри этого pipeline run.

## 8 Edge cases и UI Excel

17 PlayStation tests проверяют: Disc/Digital dimensions; original/Slim/Pro guide families; regional и EC suffix; same model/different color; base vs bundle; own gallery vs USB-bundle selector; repeated gallery dedup; package/stand dimensions; модель не подтверждает configuration fields; hardware facts не retail SKU; safety/QSG не User Guide; negative feature statement; color/box metadata не заменяют specs; common worker/readiness/Excel aliases.

10 product pages HTTP 200. Группы core/features используют общий renderer, конфигурация вынесена отдельно. Все 10 descriptions без support/help copy. Native Excel экспорт сохранён read-only и проверен openpyxl для структуры, затем Artifact Tool inspect/render. Sheets: категории, common source/fact audit, Готовность PlayStation, Конфигурация PlayStation, Кандидаты PlayStation, Документы PlayStation, Фото-кандидаты. Formula errors 0. Визуально проверены identity/gaps, русские labels/units, candidate sheets и gallery/lightbox. Excel не переавторивался другим движком.

## 9 Архитектура и блокеры

**Отдельный hardware-configuration framework не обоснован.** Наблюдённые различия помещаются в общий pipeline с небольшим PlayStation adapter и двумя дополнительными source scopes. Нужен дальнейший разбор hardware table rows и configuration selectors внутри адаптера, а не отдельный search engine.

Systemic blockers: regional sitemap children и Direct catalog не подключены к autonomous exact discovery; external search provider не настроен; PS5 family page не маршрутизирует revision-specific facts; Slim combined table нуждается в row routing; Portal/PULSE/текущая DualSense revision требуют canonical specs extraction; retail SKU↔CFI и scoped color/bundle photos покрыты не полностью; description extraction пока отсутствует. Наличие Fortnite PDP проверено отдельно, поэтому его pipeline miss является discovery defect, а не реальным отсутствием official evidence.

Real evidence gaps: retail bundle/region/color нельзя вывести из bare CFI; discontinued original revisions не обязаны иметь актуальную коммерческую PDP; Safety Guide не заменяет User Guide; чужой цвет/комплект нельзя подтвердить по family gallery. Требуются exact official/dealer evidence или review. До устранения названных blockers итог — **PlayStation adapter not ready**.

## 10 Regression и Git

Полный offline regression: {(' / '.join(regression['result'])+', immutable source tree: '+str(regression['source_tree_unchanged'])) if regression else 'ожидается'}. Command `.venv/Scripts/python.exe -m tests`, Chromium из `.venv/playwright-browsers`. Авторизованный Stage 66 migration record добавлен в существующий protected-hash registry; старые reports и hashes не переписаны. Git diff check и commit/push выполняются только после полного PASS. Commit hash публикуется отдельным итогом после операции, чтобы отчёт не содержал самоссылочный hash.
'''
(r/'report.md').write_text(report,encoding='utf-8')
print('Stage 66 report:',summary['stage_acceptance'],'adapter not ready; 10 frozen rows; configuration safety invariants PASS')
