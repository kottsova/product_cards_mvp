"""Reproducible audit from fresh worker results and offline QA, with failures visible."""
import json,hashlib
from pathlib import Path
from collections import Counter
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from product_tool.electrolux_page import parse
R=Path(__file__).parent
def read(p):return json.loads(p.read_text(encoding='utf8'))
summary=read(R/'release_live/summary.json');stability=read(R/'release_stability/summary.json');reg=read(R/'regression_release.json');gallery=read(R/'gallery_audit.json');docs=read(R/'document_audit.json')
rows=[read(p) for p in sorted((R/'release_live').glob('*/result.json'),key=lambda p:int(p.parent.name))]
old=Path('reports/electrolux_stage78/qualified_live');before={p['id']:p for p in read(old/'summary.json')['rows']}
roots={1:'UK PDP → catalog redirect; IE absent from allowlist, regional breadth starved; duplicate photo host allowlist; same-PNC source label collision',2:'Same owner/section/PNC publishes two unequal Push Button Functions lists; metadata semantics unresolved',10:'Exact revision owner found through published menu; own image linked to larger published derivative; base-PDP technical equivalence unproven'}
qualified={'dataset_unchanged':(R/'dataset.json').read_bytes()==Path('reports/electrolux_stage78/dataset.json').read_bytes(),'live_official_models':sum(bool(d['evidence'].get('live_success')) for d in rows),'usable_for_review':sum(d['readiness']['confirmed_specs']>=3 and sum(p['selected'] for p in d['photos'])>=1 for d in rows),'ready_cards':sum(d['readiness']['verdict']=='export_ready' for d in rows),'byte_verified_gallery':gallery['byte_verified'],'confirmed_gallery':gallery['selected'],'second_run_count':len(stability['rows']),'second_run_live':all(d['live_success'] for d in stability['rows']),'second_run_stable':all(d['stable'] for d in stability['rows']),'no_duplicates':all(not any(d['duplicates'].values()) for d in stability['rows']),'sources_unchanged_in_qualified_batch':summary['source_tree_unchanged'],'sources_unchanged_in_second_run':stability['source_tree_unchanged'],'regression_passed':reg['exit_code']==0 and reg['source_tree_unchanged'],'production_verdict':'Electrolux adapter not ready','initial_live_attempt':'full_live stopped after 337 seconds without trace progress at UK-catalog→PDP transition; process tree recorded; no received denial/challenge/status proof. One fresh session retry, no replay. Root cause remains unqualified.'}
qualified['audit_pass']=all([qualified['dataset_unchanged'],qualified['live_official_models']==10,qualified['usable_for_review']>=9,qualified['byte_verified_gallery']>=18,qualified['second_run_count']>=5,qualified['second_run_live'],qualified['second_run_stable'],qualified['no_duplicates'],qualified['sources_unchanged_in_qualified_batch'],qualified['sources_unchanged_in_second_run'],qualified['regression_passed']])
# An unqualified native driver stall is still a live stability blocker. Do not
# silently drop a failed live attempt merely because a later session succeeded.
qualified['live_access_fully_qualified']=False
qualified['stage79_pass']=qualified['audit_pass'] and qualified['live_access_fully_qualified']
(R/'qualification.json').write_bytes((json.dumps(qualified,ensure_ascii=False,indent=2)+'\n').encode())
table=['| model | было specs/photos | root cause | PNC/revision | specs | photos confirmed/bytes | conflict | стало |','|---|---:|---|---|---:|---:|---:|---|']
for d in rows:
 p=d['input'];e=d['evidence'];i=e['identity'];r=d['readiness'];b=before[p['id']];photos=sum(x['selected'] for x in d['photos']);verified=sum(bool(x.get('accepted')) for x in e.get('image_measurements',[]));relation=f"PDP {i.get('product_code')} / source revision {i.get('revision')} / {i.get('product_code_relation')}"
 if i.get('requested_revision_identity_confirmed'):relation+=f"; exact requested owner {i['requested_pnc']} confirmed, specs partial"
 table.append(f"| {p['model']} | {b['specs']}/{b['photos']} {b['readiness']} | {roots.get(p['id'],'Stable native PDP; no identity threshold change')} | {relation} | {r['confirmed_specs']} | {photos}/{verified} | {r['conflicts']} | {r['verdict']} |")
eod=next(d for d in rows if d['input']['id']==10);ev=eod['evidence'];url=next(s['url'] for s in eod['sources'] if s['source_key']=='electrolux');capture=next(c for c in ev['captures'] if c['url']==url);html=(R/'release_live/10/captures'/capture['file']).read_text(encoding='utf8');base_doc,base_ev=parse(html,url,'EOD6C46K2','949499578','UK')
extraction={'origin':'offline parser diagnostic on actual live EOD PDP; base-PNC counterfactual is not frozen-input live success','frozen':{'raw':len(ev['raw_facts']),'accepted_raw':len(ev['accepted_facts']),'rejected_raw':len(ev['rejected_facts']),'confirmed_specs':eod['readiness']['confirmed_specs'],'confirmed_photos':sum(p['selected'] for p in eod['photos']),'revision_identity_confirmed':ev['identity'].get('requested_revision_identity_confirmed',False)},'published_base_counterfactual':{'raw':len(base_ev['raw_facts']),'accepted_raw':len(base_ev['accepted_facts']),'rejected_raw':len(base_ev['rejected_facts']),'mapped_fields':len(base_doc.attributes),'gallery_items':len(base_ev['gallery_inventory'])},'inventory':ev.get('pnc_inventory'),'revision_owner':ev.get('requested_revision'), 'rejection_reasons':dict(Counter(r['reason'] for r in ev['rejected_facts']))}
(R/'extraction_audit.json').write_bytes((json.dumps(extraction,ensure_ascii=False,indent=2)+'\n').encode())
conflicts={d['input']['model']:d['evidence'].get('source_field_collisions',[]) for d in rows if d['readiness']['conflicts']}
(R/'conflict_audit.json').write_bytes((json.dumps(conflicts,ensure_ascii=False,indent=2)+'\n').encode())
manuals=['| model | manual | документы verified/inventory | причина |','|---|---|---:|---|']
for d in rows:
 e=d['evidence'];inventory=e.get('document_inventory',[]);reason='';
 if d['input']['id']==4:reason='User Manual не опубликован в просмотренной PDP inventory; не заменён fiche/label'
 if d['input']['id']==8:reason='Guide URL опубликован, download Network request failed; реальный технический blocker'
 if d['input']['id']==10:reason='Revision identity подтверждена; связь базовых документов с revision не доказана'
 manuals.append(f"| {d['input']['model']} | {e['manual_status']} | {sum(bool(x.get('verified')) for x in inventory)}/{len(inventory)} | {reason} |")
report=f'''# Stage 79 — Electrolux discovery / PNC recovery

**Stage 79 PASS не поставлен:** контрольный audit данных {"PASS" if qualified['audit_pass'] else "FAIL"}, но один actual live session stall остался без квалифицированного root cause. **Electrolux adapter not ready.** GitHub release не выполнен: пользователь разрешил commit/push после Stage 79 PASS.

## Dataset и границы наблюдений
10 Stage 78 inputs сохранены byte-for-byte, SHA256 `{hashlib.sha256((R/'dataset.json').read_bytes()).hexdigest()}`. Row 10 по-прежнему synthetic `94949957800`; это не доказанный supplier SKU. `affected_final` — три затронутые модели. `release_live` — новый actual live batch, `release_stability` — шесть fresh повторов в той же DB с persistent profile. Replay не использован ни в одном qualification run. `full_live` — сохранённый failed diagnostic, не successful batch. `affected_live` и `affected_qualified` — промежуточные diagnostics, не release qualification.

## EFI61141B
UK native catalog публикует `EFI61141B → 914932044 → PDP link`, но PDP URL перенаправляет в каталог с обычным 200; PDPContainer отсутствует, reject. Exact Ireland PDP обнаружена из regional official catalog, через опубликованный `/10-kg-washing-machine/efi61141b/` link, без guessed product slug. Ireland отсутствовала в adapter/photo allowlists; UK sitemap раньше расходовал бюджет до other-region phase. Теперь regional catalogs идут до глубоких sitemaps, candidate URLs дедуплицируются.
UK catalog и IE PDP печатают один base PNC; общий route подтверждает product relation. Электрические/regulatory данные Ireland удержаны candidates; региональная эквивалентность не объявлена. Галерея exact model/White byte-verified, supplier finish не придуман. В инструкции проверен EN User Manual. Новый root cause: два различных списка Push Button Functions под одним label/PNC, как у EF7742OBI. Conflict сохранён. Все query/provider/source type/requested/final URLs и accept/reject reasons в row 1 trace.

## EOD6C46K2
PDP не бедная. Frozen input: {extraction['frozen']}. Offline counterfactual **для опубликованного base PNC**, не для synthetic input: {extraction['published_base_counterfactual']}. Native FullSpecification и TopArea gallery доступны; Organization/Product JSON-LD не смешиваются с SSR владельцем. Revision inventory публикует `94949957800` и `94949957801`, но не утверждает общую technical/gallery/document equivalence. Exact requested revision identity подтверждена через observed menu route и native appliance owner. Техническая конфигурация остаётся partial: base-PDP specs/docs не переносятся. Одно фото revision подтверждено relation между own thumbnail и большой published PDP derivative — тот же asset UUID/file, только WS_PV/WS_PN, без crop/query. Миниатюра ниже прежнего size threshold; использован только уже опубликованный большой derivative, URL не сконструирован. Остальные base-PDP images остаются candidates. Raw→accepted→rejected полностью в extraction_audit/result evidence.

## EF7742OBI conflict
Оба ряда относятся к одному PDP/FullSpecification/Other, owner EF7742OBI, PNC `914580516`, revision не напечатана. Первый список: `Delayed Start, ON/OFF, Plus Steam, Prewash, Soft Plus, SPIN SELECTION, Start/Pause, TEMP SELECTION, TIME MANAGER`. Второй: `Cold, Night, NO SPIN, Plus Steam, Prewash, RINSE HOLD, Soft plus, SPEED3, Start/Pause, Temperature 5`. Это не разные revisions и не повтор одинаковой DOM строки. Source label/semantics collision: руководство различает кнопки и опции, второй список также содержит нерасшифрованные служебные названия. Нет оснований объявлять списки эквивалентными или исчерпывающими. Нормализованный конфликт `функции_управления` сохранён; union/rename/first-value selection не применяются. Точные URL/section/row indexes/values — conflict_audit.json; EN control-panel PDF preview — qa.

## PNC / revision
Published numeric product code, nine-digit base и two-digit printed revision сохранены отдельно. PNC не padded. Model inventories разрешают несколько PNC/revisions; весь native modelData.appliances list сохраняется, menu сверяется с payload. Ничего не выбирается первым автоматически. Exact input PNC candidate имеет приоритет перед совпадением только модели; неправильный PNC не прекращает discovery. Adapter выбирает **requested PNC** в опубликованном visible menu, делает fresh GET наблюдённого URL и проверяет unique native appliance owner/code/models. Подчинённые spare-part specs/docs исключены. Live research отдельно проверил `94949957800/01` и `94403205100/01`: routes отвечают 200, native owners содержат code/models/name/image/explodedViewSections; полного appliance spec payload нет. Parts lists revisions различаются. Одинаковые Energylabel-UK-BJB PDF links даже у разных oven models находятся в spare-part grid и не считаются appliance documents. Exact eleven-digit PDP/doc relation имеет приоритет; base-only specs не становятся revision specs после inventory/identity proof. Официальные model URL берутся только из published robots→sitemapindex→Model sitemap links. XML ограничен 3 MB, 14 children, deadline и текущим RequestBudget; incremental same-session catalog cache сохраняет pending children. Native inventory PDP и каждый product PDP открываются свежим navigation. EOF6P46X inventory подтверждает множество base/revisions; это не spec equivalence. См. revision_owner_audit.json.

## HTTP / browser / replay и stability limitation
Default verified requests на UK/IE/shop: ReadTimeout 8 s, **ответ/status не получен**, поэтому 403/429 не приписываются серверу. Visible persistent Chrome с system CA даёт обычные 200. Один context на batch, общий context/cookies для всех товаров, только количество cookies экспортировано. Guards/pacing/cooldowns не сняты: challenge 30 min, rate limit 60 min, HTTP denial 360 min, exact-host scope; manual/fatal independent. Received-main-200 timeout может быть revalidated snapshot без второго navigation, как существующий Dreame flow; challenge/429/foreign redirects остаются stops.

Первый полный attempt `full_live` остановлен через 337 s после старта: последние примерно 314 s trace не менялся после UK catalog→PDP. Сохранены DB/trace/captures и task-process inventory; остановлен только собственный process tree. Один новый actual session retry не использовал replay. В последующих batch stack timer фиксирует обычную работу разных этапов; offline timing XML fingerprint ~0.16 s опроверг предположение, что это постоянный regex hang. Original stalled attempt stack отсутствует; root cause между driver/session/network не доказан. **Не считаем проблему live access полностью закрытой.** Успешные последующие runs показывают работоспособность visible path, а не стирают initial failure. Нового transport/framework не построено.

## До / после
{chr(10).join(table)}

Итого actual live official models {qualified['live_official_models']}/10, usable evidence для controlled review {qualified['usable_for_review']}/10, ready {qualified['ready_cards']}/10. Usable не равно ready: конфликтные строки требуют review, synthetic revision остаётся partial. False variant facts не добавлены; thresholds/manual policy неизменны.

## Gallery / documents
Byte-verified images {gallery['byte_verified']}, confirmed/selected {gallery['selected']}; candidate identity отдельно. SHA256/full decode/content type/format/width/height/file size проверены, broken/placeholder не принимаются. См. gallery_audit и contact sheet.
User Manual, Installation Instructions, Product Fiche, Energy Label, Safety отдельно; Installation Manual не становится User Manual. Manuals optional; не входят в readiness blockers.
{chr(10).join(manuals)}

## Second run
{json.dumps(stability['rows'],ensure_ascii=False,indent=2)}
Повтор в той же DB: source URLs, normalized values/units/status/conflicts, gallery bytes/selection, document bytes/language, PNC relation и readiness сравниваются; counts дубликатов source/photo/document = 0 при успешном результате. Один persistent profile, один context этого run; context закрыт штатно.

## Regression / verdict / Git
Полный offline regression: {reg['result']}, exit={reg['exit_code']}, source tree unchanged={reg['source_tree_unchanged']}. Адресные тесты включают exact-PNC ordering, inventory owner/menu match, negative revision/color/region transfer и lookalike image hosts. Native UI/Excel QA отдельна от actual live.
**Electrolux adapter not ready**: unresolved initial driver/session stall, same-PNC source label collisions EFI61141B/EF7742OBI, EOD6C46K2 exact-revision technical equivalence отсутствует; default HTTP не квалифицирован. Stage 79 PASS не поставлен, commit/push не выполнены. Базовый HEAD `0c4c6769d5bc89b0f7a9ab0adc218fabf7ef12d8`; изменения и проверяемые artifacts сохранены в working tree.
'''
(R/'REPORT.md').write_bytes(report.encode());print(qualified)
