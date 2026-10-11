"""Stage 78 audit summary from actual live evidence; release gate requires full regression."""
import json,hashlib,re
from pathlib import Path
from bs4 import BeautifulSoup
R=Path(__file__).parent;L=R/'qualified_live'
def read(p):return json.loads(p.read_text(encoding='utf8'))
summary=read(L/'summary.json');first=read(R/'first_live_v1/summary.json');rows=[read(L/str(i)/'result.json') for i in range(1,11)]
reg=read(R/'regression_release.json') if (R/'regression_release.json').exists() else {'exit_code':None,'source_tree_unchanged':None,'result':['pending']}
gallery=read(R/'gallery_audit.json');docs=read(R/'document_audit.json');assert summary['dataset_sha256']==(R/'dataset.sha256').read_text().strip()
pncs={}
for region,url in [('UK','https://shop.electrolux.co.uk/model/m/EOF6P46X'),('SE','https://shop.electrolux.se/model/m/EOF6P46X')]:
 p=R/(hashlib.sha256(url.encode()).hexdigest()[:12]+'.html');s=BeautifulSoup(p.read_text(encoding='utf8'),'html.parser');codes=list(dict.fromkeys(x.get('aria-label','') for x in s.select('button[role="menuitem"][aria-label]') if re.fullmatch(r'\d{11}',x.get('aria-label',''))));pncs[region]={'url':url,'pnc_versions':codes,'relation':'Actual live official model-specific PNC menu; no specs equivalence assumed'}
qualified={'stage':78,'audit_verdict':'PASS' if reg.get('exit_code')==0 and reg.get('source_tree_unchanged') else 'pending regression','adapter_verdict':'Electrolux adapter not ready','actual_live_pdp':sum(r['live_success'] for r in summary['rows']),'cards_ready':sum(r['readiness']=='export_ready' for r in summary['rows']),'confirmed_specs':sum(r['specs'] for r in summary['rows']),'byte_verified_selected_photos':gallery['selected_count'],'verified_documents':sum(bool(x.get('verified')) for x in docs['documents']),'manual_statuses':{str(r['id']):r['manual'] for r in summary['rows']},'context':{k:summary[k] for k in ('session_id','contexts','navigations','cookies_before_count','cookies_after_count','context_closed')},'frozen_dataset_sha256':summary['dataset_sha256'],'framework_required':False,'pncs':pncs,'regression':{k:v for k,v in reg.items() if k!='source_manifest'},'blockers':['EFI61141B exact UK PDP redirects to catalog; other-regional/external exact source not recovered within bounded discovery','EF7742OBI same official Push Button Functions label has two different lists; held as conflict','Exact 11-digit PNC/revision-sensitive configuration resolution not qualified; row 10 is an explicit synthetic revision request, correctly partial','Default plain HTTP transport fails before response in this environment; controlled Chrome data acquisition works, default HTTP production access not qualified'],'offline_only':'30 fixture/transport edge tests and gallery/PDF/UI QA are not fresh live successes'}
(R/'qualification.json').write_bytes((json.dumps(qualified,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
table=['| ID | Модель / вход | PNC PDP | Live | Было specs → стало | Фото | Инструкция | Готовность |','|---|---|---|---|---|---|---|---|']
for row,old in zip(rows,first['rows']):
 p=row['input'];ev=row['evidence'];now=summary['rows'][p['id']-1];table.append(f"| {p['id']} | {p['model']} / {p['article']} | {ev['identity'].get('product_code','—')} | {'Да' if now['live_success'] else 'Нет'} | {old['specs']} → {now['specs']} | {now['photos']} | {now['manual']} | {now['readiness']} |")
text=f'''# Stage 78 — Electrolux baseline audit

Audit verdict: **{qualified['audit_verdict']}**. Adapter verdict: **Electrolux adapter not ready**.
Основание: Dreame `86325a806d760ecf29230f6195a67559bdb94303`; frozen dataset SHA256 `{summary['dataset_sha256']}`.

## Baseline и происхождение данных

`baseline.json`: обычный, неизменённый `run_once()` для EFI61141B до добавления адаптера — job error, not_ready, specs/photos/documents 0. DNS не запускает guessed search без проверенного dealer URL. Отдельный Chrome probe показал redirect exact EFI61141B URL в каталог: старый search index не является live PDP.
`exact_pdp_baseline/baseline.json`: повторён тот же **неизменённый** worker для реально доступной EOF6P46X с official PDP — те же 0 specs/photos, error/not_ready. Причина обоих baseline: Electrolux official dispatch отсутствовал. Research PDP/identity не были подставлены в этот результат.
Исходный артикул EOF6P46X, model EOF6P46X, product code / base PNC 944032051, regional source UK, 11-digit revision не напечатана. Это значения последующего actual native research, а не успех baseline worker.

## Official structure

Regional PDP: exact `PDPContainer` в `__NEXT_DATA__.props.pageProps.pageData.components`. Его `TopArea.modelId`, `productCode`, `ean`, `pageHeading` — разные identity fields. Header/footer/recommendations/reviews не владеют спецификациями товара. JSON-LD в проверенном UK PDP — Organization, не Product; его name/logo нельзя использовать как модель/галерею.
`FullSpecification.attributes`: section → label → infoText. `Specification`, Swedish `Specifikationer` — feature/marketing prose, не технические пары. Сохраняются в raw/rejected inventory. KeySpecification не перекрывает detailed rows.
`TopArea.imageGallery.galleryItems`: exact published product gallery через regional `/services/eml/transform/...`. `DocumentsContent`: `productCode` может быть **model name**, `pnc` — numeric PNC; их нельзя считать одним полем. `document.documents` и `installation.documents` разделены.
Documents: `productinformation.electrolux.com` datasheets; published `electrolux.bynder.com` PDF guides; `support.electroluxgroup.eu/external/compliance-documents/GBEnergyLabel/...` label/fiche. 301 требует безопасного redirect handling. `/support/user-manuals/` и `/support/product-fiches/` — отдельные inventories; fiche UI просит первые 9 цифр PNC. Official parts site `/model/m/...` публикует 11-digit PNC versions.
`robots.txt` публикует `.../globalassets/sitemaps/.../sitemapindex.xml`; не guessed `/sitemap.xml` (последний probe неуспешен). Published site search `searchPageName` + наблюдённый input `q` используются перед catalog; общий external `LGBrowserSearch` — после official miss и support, DNS — последним.

## Identity и реальные PNC findings

Marketing model, published numeric product code/base PNC, optional 11-digit service revision, EAN, region и family сохраняются отдельно. Если supplier PNC не задан, карточка описывает **опубликованный региональный продукт с его PNC**, без утверждения о неизвестной supplier revision. Если PNC задан, сравнение точное; 9 цифр не дополняются `00`.
Actual official EOF6P46X parts menus UK/SE: {', '.join(pncs['UK']['pnc_versions'])}. Один model name связывается с несколькими base PNC и revisions. Это **не доказательство** равенства технических конфигураций. Поэтому dimensions/energy/finish/voltage/accessories/documents и programs/capacity неподтверждённого PNC не переносятся. При partial остаётся только классификация модели; thresholds сохранены.
Same-model UK/IE research PDP показал EOF6P46X + 944032051 в обоих регионах; это supplemental research, не injected production discovery и не доказательство одинаковости всех региональных specs. Native UK и SE parts relation также проверены отдельно.
Строка 9: input PNC 914606627 → official EWD746PCBI / 914606627, exact base-product relation. Строка 10: input 94949957800 специально сформирован как **synthetic revision challenge** до первого batch, не выдан за существующий supplier SKU. PDP печатает 949499578: revision не подтверждена, partial. Dataset bytes не менялись.

## Extraction, energy, installation, documents

Общий pipeline сохранён: Excel importer → ordinary queued worker → existing policy/browser/search/dealer → native adapter → normalization/resolution → evidence/readiness → native UI/export. Нового framework нет.
Исправлены доказанные общие root causes: installation_dimensions больше не product_dimensions; only-machine mass — отдельный qualifier; bounded safe Chrome binary redirects — вместо возврата первого 301. LED color canonical label использует существующий backlight_color, не color корпуса. Другие бренды/thresholds не переопределены.
PNC raw rows сохранены с section/raw label/value до canonical mapping; Русский словарь label поддерживает washing/drying/dishwasher/fridge/oven/hob/vacuum. Product, niche и package scopes раздельны. Swedish bare device mass 4.998 kg и net mass 7.273 kg не конфликтуют как одна сущность. Actual EOF6P46X: width product 595 mm vs niche 560 mm; height product 594 mm vs niche 590 mm. Явный `max` не теряется. Неуказанные единицы/период/оси не достраиваются.
Programs — один список в parent `Программы`; функции управления отдельно. SupportModule/FAQ/troubleshooting/reviews не попадают в ProductDescription/specs.
Energy: annual consumption, 100 wash cycles, 100 wash/dry cycles и conventional/fan oven cycles — разные поля. Spin class и noise class не energy class. PDP source label не выдаётся за новую шкалу. EDHI618WD actual Energy Label: **A++ на A+++–D, 392/2012**, 235 kWh/year; fiche — 234.7, basis 160 drying cycles. E52LE100S actual label: **E на A–G**, 94 kWh/100 cycles, 9.9 L/cycle, 47 dB/C noise class. Стандарты и периоды не конвертируются/не смешиваются. Fiche dimensions в cm с округлением не заменяют PDP exact mm.
Energy Label/Product Fiche/Specification Sheet/User Manual/Installation Drawing сохранены как разные types, с language, model, PNC, region, source relation, byte-verification/SHA. Installation drawing не основной manual и не primary product photo. PDF facts не merged автоматически с PDP specs. Safety не подменяет User Manual.
В финале: {qualified['verified_documents']} verified PDFs из {len(docs['documents'])} inventory entries. EN User Manuals actual downloaded для IDs 2,3,5,6,7,9; ID4 — User Manual отсутствует в завершённом PDP inventory (bounded scope, не утверждение отсутствия во всей сети); ID8 — technical PDF failure; ID1 — exact source не получен; ID10 — PNC revision relation не проверена. RU guide отдельно не подтверждён. Manual optional, ID4/8 ready при этих статусах.

## Frozen dataset и результаты

10 разных моделей: 2 washers, dryer, dishwasher, fridge, oven, hob, vacuum, washer-dryer по PNC и ещё oven с revision challenge. Набор заморожен до первого job; предварительная ошибка подготовки DB случилась до jobs и dataset не изменила.
First actual pass `first_live_v1`: 9/10 PDP, 16 byte-verified selected gallery assets; normalization collisions и 301 documents наблюдались честно. `final_live` — diagnostic run до окончательного document-field semantics fix, не release результат. **Только `qualified_live`** — итог: {qualified['actual_live_pdp']}/10 actual fresh PDP, {qualified['cards_ready']}/10 ready, {qualified['confirmed_specs']} resolved confirmed fields, {gallery['selected_count']} selected byte-verified images. Catalog cache — только same-session discovery; PDP всегда fresh. Captures/offline parser tests не считаются live success.

{chr(10).join(table)}

Job/readiness, exact source URLs, raw/accepted/rejected facts, photos, typed documents, query/provider/accept/reject/reason/identity traces и dealer reason — в `qualified_live/ID/result.json`. Dealer не запускался для optional manual gap/доступного official PDP. ID1 common DNS вернул missing verified dealer URL; accepted dealer evidence 0.
Не готовы: 1 — redirected/missing exact PDP и bounded discovery/fallback не восстановил его; 2 — два разных official `Push Button Functions` списка, оставлены conflict; 10 — partial revision и недостаток допустимых variant facts/gallery. Остальные 7 естественно ready, без снижения thresholds.

## Edge cases и границы qualification

1. Same model/different PNC: actual UK/SE parts menus + conservative test, no transfer energy/physical/config fields.
2. Same model/different region: actual UK/IE owner relation + explicit region negative fixture.
3. Product/install/package axes: actual oven/fridge/hob, separate normalization keys.
4. Old/new energy: actual old A+++–D dryer PDF vs new A–G dishwasher PDF, units/periods separate.
5. Different finish: mismatched input color rejects PNC facts/gallery; LED red does not alter black hob finish.
6. Family vs exact: actual EFI61141B redirect and native catalog; ProductList/Organization cannot prove exact product.
30 offline fixture/transport tests cover these cases, document URL wrong PNC, wrong owner, manual type ownership, foreign/active-stop redirect refusal, explicit no-redirect, bounded loops. Они не заменяют live acquisition.
Финальная Chrome session: contexts {summary['contexts']}, navigations {summary['navigations']}, cookie **counts only** {summary['cookies_before_count']}→{summary['cookies_after_count']}, closed {summary['context_closed']}. Наблюдённых official 403/429 в final acquisition нет; default HTTP probe дал network errors до ответа. CAPTCHA автоматизированно не решалась; access guards/cooldowns не снимались.

## UI / Excel / визуальная проверка

`qa_ui_excel.json`: native TestClient проверил все 10 cards; workbook `Electrolux_Stage78.xlsx`, 15 sheets, formula errors 0. Русские canonical labels, parent groups и отдельные metadata/typed documents. 12 screenshots по 6 карточкам; визуально проверены identity/specs, actual gallery contact sheet (16 assets, включая один model + included-accessories infographic), EN manual cover и old/new energy labels. Файлы images/PDF измерены и SHA сверены; standalone diagram/accessory не primary product image. No supplier-color claim без evidence.

## Нужен ли отдельный PNC/document framework?

**Нет.** Существующие typed evidence, SourceDocument/ProductDocument, jobs, resolution и UI/export достаточны. Нужны небольшие brand-specific PNC relations/document ownership rules в адаптере, дальнейшая exact revision/support qualification и recovery после official miss. Parts menus — typed relations, а не разрешение переносить specifications между ними.

## Regression и verdict

Полный regression: {reg.get('result')}, exit {reg.get('exit_code')}, source tree unchanged {reg.get('source_tree_unchanged')}; offline real-network guard активен. `git diff --check` проверяется перед commit. Исторические reports/datasets не правились; test preservation registry расширен append-only только на Stage78 authorized files.
Audit PASS отделён от production qualification: **Electrolux adapter not ready**. Блокеры: exact discovery после redirect/official miss, настоящий source conflict EF7742OBI, неподтверждённый exact revision path, не квалифицированный default HTTP access. Manual RU/отсутствие instruction не являются readiness blocker. Commit/push и HEAD==origin/main проверяются после full regression PASS.
'''
(R/'REPORT.md').write_bytes(text.encode('utf8'));print({k:qualified[k] for k in ('audit_verdict','actual_live_pdp','cards_ready','confirmed_specs','byte_verified_selected_photos','verified_documents')})
