"""Evidence-derived Stage 72 audit, explicitly separating live and offline modes."""
import json,hashlib,subprocess
from pathlib import Path
R=Path(__file__).parent
def read(name):return json.loads((R/name).read_text(encoding='utf8'))
base=read('baseline.json');first=read('first_pass.json');early=read('live_final.json');last=read('live_release.json');offline=read('offline_parser.json');artifact=read('artifact_verification.json');parts=read('part_number_findings.json');doc=read('document_probe.json');photo=read('photo_verification.json')
reg=read('regression_release.json') if (R/'regression_release.json').exists() else {'exit_code':None,'result':['Pending'],'source_tree_unchanged':None}
data=(R/'frozen_inputs.json').read_bytes();digest=hashlib.sha256(data).hexdigest();assert digest==(R/'frozen_inputs.sha256').read_text().strip()
rows=json.loads(data)['rows'];assert len(rows)==10
def official(x):return any(s['source_key']=='hyperx' and s['match_level'] in {'exact_variant','model_confirmed'} and not s['error'] for s in x['sources'])
live_ids=[x['id'] for x in last['rows'] if official(x)];ready=[x['id'] for x in last['rows'] if x['readiness']['verdict']=='export_ready']
partition=all(len(x['evidence']['raw_specs'])==len(x['evidence']['accepted_specs'])+len(x['evidence']['rejected_specs']) for x in offline['rows'])
summary={'stage':72,'audit':'PASS' if reg['exit_code']==0 and reg['source_tree_unchanged'] and partition and artifact['guarded_check']['network_requests']==0 else 'PENDING','adapter_verdict':'HyperX adapter not ready','baseline_parent_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'frozen_input_sha256':digest,'baseline':{'job':base['jobs'][0]['status'],'source_identity':next(s['match_level'] for s in base['sources'] if s['source_key']=='hyperx'),'raw_facts':len(base['facts']),'old_readiness':base['readiness']['verdict']},'first_pass_live_official_models':sum(official(x) for x in first['rows']),'early_actual_live_official_models':sum(official(x) for x in early['rows']),'early_actual_ready_models':sum(x['readiness']['verdict']=='export_ready' for x in early['rows']),'last_actual_live_official_models':len(live_ids),'last_ready_ids':ready,'last_not_ready_ids':[x['id'] for x in last['rows'] if x['id'] not in ready],'last_confirmed_specs':sum(x['readiness']['confirmed_specs'] for x in last['rows']),'offline_parser_confirmed_specs':sum(x['readiness']['confirmed_specs'] for x in offline['rows']),'raw_partition_verified':partition,'manual_cards_status':'Не проверена','quick_start_candidate_ids':[4],'document_download_error':doc.get('error'),'image_byte_verified':sum(bool(x['verified']) for x in photo),'guarded_network_requests':artifact['guarded_check']['network_requests'],'active_stops':artifact['guarded_check']['active_stops'],'regression':{k:v for k,v in reg.items() if k!='source_manifest'}}
(R/'acceptance_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')
table=[]
for x,f,o in zip(last['rows'],first['rows'],offline['rows']):
    i=x['id'];p=x['input'];source=next((s['url'] for s in early['rows'][i-1]['sources'] if s['source_key']=='hyperx'),'')
    gap='—' if i in ready else '429 / active cooldown' if i>=6 else '; '.join(x['readiness']['gaps'])
    prior='exact / 23 raw facts' if official(f) else 'official URL needed'
    table.append(f"| {i} | {p['article']} | {p['name']} | {prior} | {x['readiness']['confirmed_specs']} | {len(x['evidence'].get('exact_photo_assets',[]))} | {x['job']['status']} | {x['readiness']['verdict']} | {gap} |")
urls='\n'.join(f"- ID {x['id']}: {next((s['url'] for s in x['sources'] if s['source_key']=='hyperx'),'')} — {x['evidence'].get('model_relation')}, {x['evidence'].get('configuration_relation')}" for x in early['rows'])
text=f"""# Stage 72 HyperX baseline audit

**Audit {summary['audit']}. HyperX adapter not ready.** Общий pipeline переносится на HyperX с небольшими brand route/parser/presentation bindings. Отдельный configuration-resolution framework не нужен. Последний actual live-run получил official data для 5/10, предыдущий actual live-run — 10/10 (9 exact retail configurations). HTTP 429 и сохранённый cooldown препятствуют controlled production use. Offline parser на сохранённых ответах — отдельный режим, не live success.

## 1. Baseline до изменений

Обычный `worker.run_once(database)` без injected adapters, URL или модели в новом коде: QuadCast 2 S Black, `9A273AA`. Использована уже существовавшая Stage 15 KNOWN_URLS запись, а не новый discovery результат. PDP HTTP 200: https://hyperx.com/products/hyperx-quadcast-2-s-usb-microphone . Identity `exact_variant`, job `done`, readiness `not_ready`; {len(base['facts'])} raw facts, 9 gallery renders и 5 feature images по старому parser. Color Black опубликован variant record; regional suffix/revision отсутствуют; commercial model QuadCast 2 S не равен QuadCast 2. Query variants не исполнялись: legacy lookup обходил discovery. Manual не проверена. DNS получил 401 и остановился без обхода.

Root causes: readiness учитывал только LG OFFICIAL_KEYS; HyperX exact_variant попадал в generic official_base_only; photos не выбирались; parser сохранял Unit price. Default response cap 512000 bytes ограничивал полноту payload. Baseline raw HTML, исходные jobs/facts/photos/evidence сохранены, исходный результат не переписан.

## 2. Official структура

`hyperx.com` — Shopify storefront. Homepage объявляет GET `/search` (`q`, `type=product`, `options[prefix]=last`). Robots объявляет sitemap index и product sitemap; 200 ответы сохранены. JSON-LD Product даёт selected SKU, offers, merchant GTIN и numeric Shopify productID. `script[data-product-json]` содержит option-labelled variants и media. Explicit `table.tech-specs-table` и technical tab дают section/raw label/value. Gallery и feature infographics разделены.

Footer `/pages/support` публикует https://supportcenter.hyperx.com и отдельно HP support для OMEN PCs/monitors. HyperX accessories обслуживает собственный Support Center (Sprinklr SSR/JS), не автоматически HP product support. Категории Headset/Keyboard/Mouse/Microphone/Controller получены live 200. SSR показывает десять популярных articles на категорию. Search link существует, но executable query parameter не объявлен в HTML; полный model/manual inventory требует browser/API binding. HP newsroom и официальный HyperX press содержат отдельные part-number tables. Published guide download host — `files.hyperx.com`.

Other-region roots остаются independent official candidates. В observed frozen run региональное расширение не было выполнено до конца в 20-секундном official budget; отсутствие RU retail payload не объявляется отсутствием товара. Общий Google browser fallback после exact official miss вызван отдельно: `no_candidates`; полноценный successful search response этим результатом не доказан. Product-only filters также не заменяют чтение press identity relations. Dealer fallback общий DNS, 0 accepted dealer sources; seeded retail URLs не добавлялись.

## 3. Identity и part numbers

Model-level характеристики разрешены при exact commercial model, включая поколение и wired/wireless qualifier. Exact full code не нужен для общих model facts. Variant-specific color/layout/switch/physical configuration переносится только при подтверждённом выбранном variant; его Shopify record и JSON-LD offer должны иметь связанный SKU/variant ID. Selected default и другой вариант не подставляются. Explicit requested options сопоставляются отдельно; SKU/name disagreement отвергается.

Merchant SKU, HP part number, Shopify product ID и Shopify variant ID — разные relations. `#suffix` хранится буквально, без декодирования layout по суффиксу. Revision не выводится из похожего кода. В `part_number_findings.json` сопоставлены HP `Part Number` и **historical Stage 18** HyperX merchant records для Cloud III wired; этот контроль не выдаётся за fresh discovery. Cloud III Wireless `77Z46AA` не подменяется wired `727A8AA`/`727A9AA`.

Официальная HyperX [press table](https://hyperx.com/blogs/press/hyperx-alloy-origins-65-mechanical-gaming-keyboard-now-shipping-with-colorway-customizations) публикует `4P5D6AX#ACB` — Russian, Red; `4P5D6AA#ABA` — US Red; `56R64AA#ABA` — US Aqua. Это доказательство опубликованных part/configuration relations, не текущей availability и не RU gallery. [HP Cloud III press](https://www.hp.com/us-en/newsroom/press-releases/2023/hyperx-announces-cloud-iii-gaming-headset.html) — отдельный источник manufacturer part facts.

## 4. Frozen dataset и первый pass

10 строк зафиксированы до первого run. SHA256 `{digest}`. 3 гарнитуры, 3 keyboard configurations (в том числе сложный RU SKU), 2 мыши, микрофон и controller. Baseline `9A273AA` исключён из десятки. В input нет PDP URLs. Dataset после freeze не менялся. Первый обычный pass: 1/10 official source, 0/10 ready; причина остальных — отсутствие старого KNOWN_URLS route. Новая discovery использует published forms/sitemaps и shared parsers, а не model URL hardcode.

## 5. Последний actual live-run

| ID | Входной SKU | Commercial model / configuration | Первый pass | Live confirmed specs | Exact gallery links | Job | Readiness | Главный gap |
|---:|---|---|---|---:|---:|---|---|---|
{chr(10).join(table)}

Manual status всех десяти: `Не проверена`. Dealer confirmed: 0. Gallery counts означают identity-scoped links из actual PDP; не скачанные/byte-verified images. Image measurement attempts остановлены общим действующим HyperX cooldown: {summary['image_byte_verified']} byte-verified images. Разные color/layout остаются candidates. Existing photo selection сохраняется при повторной обработке.

Предыдущий independent actual live run (`live_final.json`, до support completion) получил 10/10 model sources, 9/10 exact configuration и 9/10 ready. Его sources:

{urls}

`offline_parser.json`: current parser на тех же saved bytes, {summary['offline_parser_confirmed_specs']} confirmed specs, 9/10 ready. Это не новый live-run. Partition raw=accepted+rejected проверен для всех 10. Последний actual live — {summary['last_confirmed_specs']} confirmed specs в 5 доступных карточках. Сводка не смешивает эти режимы.

## 6. Extraction, edge cases и UI/Excel

Component/block labels сохраняются до canonical mapping. Headphone/microphone sensitivity больше не конфликтуют; keyboard general actuation description и switch actuation distance — разные ключи. Published Aqua/Tactile vs Operation Style Linear на Origins 65 отвергнут как source contradiction. Unit price исключён. Weight с headset/base station/boom mic и microphone/stand не сворачивается в вес устройства; source ownership остаётся в значении. Dimensions сохраняют опубликованные axes, Length не становится Depth автоматически. Runtime `Up to` остаётся заявленным максимумом; неизвестный режим не превращается в 2.4GHz/Bluetooth/RGB claim. Missing sample-rate/bit-depth table coverage не восполняется marketing description.

23 meaningful offline tests: other color, US/UK/RU, wrong switch, wired/wireless, wrong generation, nearby part, Shopify numeric ID≠HP part, literal suffix, other-selected physical specs, vendor contradiction, price, metadata≠spec coverage, manual optional, shared discovery links, cooldown/no network/log preservation, UI/Excel read-back. Configuration facts из family options не становятся confirmed. Время и основная часть runtime не подтверждаются по footnote без явного mode relation.

UI HTTP200 read-back для доступных и blocked карточек, separate identity/options/candidates/documents, Russian canonical labels и parent groups. Core/features разнесены; ошибочная LG caption убрана. Excel read-back: product category sheets, sources, photos, HyperX readiness, identity relations, rejected facts, typed documents и photo candidates. Support/help content не используется как description: только PDP description, support отдельно.

## 7. Manuals

User Guide/Master Guide/Quick Start/Safety/Warranty различаются по типу; Safety не считается User Guide. Для ID4 найден опубликованный [Quick Start article](https://supportcenter.hyperx.com/articles/alloy-rise-75/hyperx-alloy-rise-75-quick-start-guide/68d6a88d1498c079f6b362f2) и PDF link. Supplementary bounded download: `{doc.get('error','')}`; PDF/model/RU content не проверены. Этот сбой не называется доказанным серверным 403/429. Полный manual inventory не завершён, поэтому нет ложного статуса «Проверена, не найдена». Manual optional и не блокирует readiness.

## 8. Access lifecycle и verdict

HyperX PDP ID6 в финальном run вернул 429 at `2026-10-10T11:34:27Z`. Existing domain cooldown `hyperx.com`, TTL1h, expires `2026-10-10T12:34:27Z` (16:34:27 Asia/Tbilisi). Stops/history не удалены и timestamps не состарены. После correction active stop становится `blocked`, не `official_url_needed`. Guarded check: 0 requests, log unchanged. Не изолировано, какой вклад внесли server policy, повторные проходы и новые HTTP sessions; rate-limit response доказан, причинный A/B не заявляется. No CAPTCHA bypass/automatic solution; CAPTCHA completion не испытывалась.

**HyperX adapter not ready**: (1) unstable HTTP access/429 и active cooldown; (2) текущая exact RU PDP/gallery relation не разрешена в bounded official path; (3) full support inventory/browser/API/manual retrieval integration не завершён; (4) runtime mode/footnote и sparse microphone table coverage требуют дальнейшего extraction audit. Manual absence само по себе не блокер карточки. Для identity/configuration нужен существующий общий слой плюс brand bindings, отдельный framework не обоснован.

## 9. Regression и Git

Regression: `{reg['result']}`; exit `{reg['exit_code']}`, source tree unchanged `{reg['source_tree_unchanged']}`. Earlier stage blocks/pins сохранены; Stage72 authorization append-only. Прерванные pre-UI/pre-label/pre-import checks сохранены отдельно и не считаются regression PASS. `git diff --check` выполнен. После audit PASS — commit `Stage 72`, push, actual remote hash equality и clean working tree; окончательный hash сообщается после commit.
"""
(R/'REPORT.md').write_text(text,encoding='utf8')
print({k:v for k,v in summary.items() if k not in {'regression','active_stops'}})
