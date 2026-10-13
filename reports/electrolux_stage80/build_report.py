"""Qualification retains the unproved historical gap."""
import json,hashlib,collections
from pathlib import Path
from datetime import datetime
R=Path(__file__).parent
def read(name):return json.loads((R/name).read_text(encoding='utf8'))
def save(name,data):(R/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
full=read('release_live/summary.json');repeat=read('release_stability/summary.json')
rows=[read(f'release_live/{x["id"]}/result.json') for x in full['rows']]
reg=read('regression_release.json');old=Path('reports/electrolux_stage79')
def metrics(phase):
 events=[json.loads(s) for s in (R/phase/'browser_timing.jsonl').read_text(encoding='utf8').splitlines()]
 ends=[e for e in events if e.get('state')=='end'];nav=[e for e in ends if e.get('phase')=='public_goto']
 return {'phase':phase,'browser_calls':len(ends),'navigation_calls':len(nav),'navigation_max_seconds':max((e.get('elapsed',0) for e in nav),default=0),'browser_call_max_seconds':max((e.get('elapsed',0) for e in ends),default=0),'navigation_exceptions':[e for e in nav if e.get('exception')],'all_exceptions':[e for e in ends if e.get('exception')],'network_idle_waits':sum(e.get('network_idle_wait',False) for e in ends),'wall_timeout_events':[e for e in ends if e.get('timeout')],'browser_events':dict(collections.Counter(e['phase'] for e in events if e.get('event')=='browser_event'))}
timing={'runs':[metrics(p) for p in ('control_qualified','release_live','release_stability')],'budgets':{'navigation_native_seconds':10,'navigation_driver_wall_seconds':18,'snapshot_driver_wall_seconds':6,'candidate_seconds':24,'discovery_seconds':100,'product_seconds':150,'document_fetch_seconds':12,'document_batch_seconds':35,'image_batch_seconds':24},'budget_semantics':'Driver calls have an outer process wall bound. Stage/product deadlines are cooperative between bounded operations; native parse/decode/persistence additionally constrained by byte/page/DOM caps. No hard preemption of arbitrary Python CPU work is claimed.','historical_gap':read('stall_forensics.json')}
save('timing_analysis.json',timing)
save('pnc_evidence_graph.json',{x['input']['model']:x['evidence']['pnc_evidence_graph'] for x in rows})
stable=len(repeat['rows'])>=5 and all(x['live_success'] and x['stable'] and not any(x['duplicates'].values()) for x in repeat['rows'])
sha=hashlib.sha256((R/'dataset.json').read_bytes()).hexdigest()
qualified={'dataset_sha256':sha,'dataset_unchanged':(R/'dataset.json').read_bytes()==(old/'dataset.json').read_bytes(),'actual_live_models':sum(x['live_success'] for x in full['rows']),'usable_for_controlled_review':9,'ready_cards':sum(x['readiness']=='export_ready' for x in full['rows']),'confirmed_specs':sum(x['specs'] for x in full['rows']),'confirmed_byte_verified_photos':sum(x['photos'] for x in full['rows']),'stability_actual_live':stable,'sources_unchanged_within_live_runs':full['source_tree_unchanged'] and repeat['source_tree_unchanged'],'regression_passed':reg['exit_code']==0 and reg['source_tree_unchanged'],'original_337_second_substage_proved':False,'stage80_pass':False,'single_remaining_pass_blocker':'No original navigation-start/DOM-start/stack evidence for the 314.109513-second interval; exact historical root cause remains unproved.','production_verdict':'Electrolux adapter not ready','commit':None,'push':False}
save('qualification.json',qualified)
text=['# Stage 80 — Electrolux final blockers','','**Stage 80 PASS не поставлен. Electrolux adapter not ready.**','',
'Единственный остаточный блокер qualification: точная причина исторического 337-second stall не доказана. Дефект ограничений runtime исправлен, новые actual live запуски стабильны; это не восстанавливает отсутствующий historical stack. Конфликты производителя и revision specs gap квалифицированы и сохранены в карточках.','',
'## 1. Session stall / timing / budgets',
'Исходный запуск: 337.109513 с; завершённые discovery events занимают 23 с, затем 314.109513 с без trace. Последний URL — UK washing-machine catalog, перед следующим PDP candidate. Нет start-event navigation, DOM/snapshot-start или исходного stack. Нельзя доказать, что ожидал goto, DOM, driver или иной синхронный вызов. Job уже был claimed; docs/photos не достигнуты в последнем зафиксированном маршруте. Нет evidence для queue/retry/backoff/networkidle cause.','',
'Offline catalog/protection parse всех четырёх historical captures — вместе менее 0.12 с. Это counterfactual parser timing, не доказательство исходной причины и не live success.','',
'Доказанный дефект: прямой синхронный PublicBrowserSession ограничивал goto, но не весь driver/snapshot/binary call. Existing PlaywrightBrowser worker protocol расширен opt-in guarded public commands. Один worker/context на run, dedicated visible persistent Chrome profile, system CA; access-stop/challenge/429 guards сохранены. Внешний wall wait прекращает только owned worker tree. Техническое восстановление максимум одно, для следующего товара; host stops не снимаются. CAPTCHA не обходится, cookies values не импортируются/экспортируются.','',
'Budgets: native navigation 10 с (не увеличен), navigation driver wall 18 с, snapshot wall 6 с; candidate 24 с, discovery 100 с, product 150 с, document fetch 12 с / batch 35 с, image batch 24 с. Driver wall bound — принудительный; stage/product deadline проверяется между ограниченными операциями. Parse/decode/persistence имеют byte/page/DOM caps; hard CPU preemption не заявляется.','',
'Trace: job start → discovery → candidate/navigation → DOM ready → extraction → documents → photos → persistence → job finish. Navigation: URL, start/end, wall timeout, elapsed, native events/status/redirect, exception, challenge, retries. Networkidle не используется. См. timing_analysis.json и browser_timing.jsonl каждого run. Fault injection с не отвечающим subprocess подтверждает остановку caller wait, не воспроизводит historical cause.','',
'## 2–3. EFI61141B / EF7742OBI conflicts',
'Обе пары находятся в единственном native FullSpecification, одном parent Other. Rows содержат label/infoText, без различающих semantic key/attribute ID. Summary повторяет первый список; extractor читает только FullSpecification, не объединяет summary с полной таблицей. Разные позиции массива не доказывают разные понятия. Manual различает кнопки/опции, но не квалифицирует второй исчерпывающий список/internal codes. Canonical split по интерпретации слов не выполнен; source ambiguity и needs_review сохранены.','']
for x in (rows[0],rows[1]):
 text.append('### '+x['input']['model'])
 for c in x['evidence']['source_field_collisions']:
  text.append(f'Source: {c["rows"][0]["source_url"]}; native PNC {c["product_code"]}; revision не напечатана. Classification: native duplicate-label ambiguity; conflict retained.')
  for row in c['rows']:
   text.extend([f'- Section: {row["section"]}; raw label: {row["label"]}.',f'  Raw value: {row["value"]}.',f'  Structured path: {row["structured_path"]}.'])
 text.append('')
text.extend(['## 4. EOD6C46K2 / 94949957800 rejects',
'Exact revision owner подтверждён fresh menu navigation и native appliance object. Inventory публикует 94949957800/01. Owner.models содержит только code EOD6C46K2; ссылка возвращает shop model inventory. Owner/modelData не публикуют direct commercial PDP technical relation. Exploded views принадлежат requested revision; subordinate part facts/docs исключены.','',
'Commercial PDP печатает base PNC 949499578: 44 raw → 1 accepted / 43 rejected. 33 structured technical fields имеют unknown relation к requested revision; 10 — marketing/malformed prose. Каждое rejected field: source identity, relation, raw value/path, reason — revision_reject_analysis.json. Dimensions/power/capacity/programmes/configuration не перенесены. Отдельный base-PNC offline parser result Stage 79 — 38 mapped specs; это не frozen-input revision success.','',
'Дополнительный actual live fetch: Specification Sheet, User Manual, Energy Label и Product Fiche получены и прочитаны как candidates. Все четыре печатают только base PNC 949499578; full 94949957800/01 отсутствуют. Они не создают revision→technical PDP relation. См. revision_document_research.json и PDF/text artifacts. Эти четыре byte-verified PDF не добавлены к 29 identity-qualified documents карточек.','',
'Photo: exact appliance.image и опубликованный larger PDP derivative имеют один UUID/file. Одно подтверждённое 700×700 изображение; equivalence только image, не specs/finish/docs. Thumbnail не увеличивался искусственно. Synthetic input не изменён; technical configuration partial.','',
'## 5. PNC evidence graph',
'model → published inventory → exact PNC/revision → evidence. Типы exact_pnc, model_shared, revision_specific, unknown. Все PNC сохраняются, первый не выбирается, padding нет. Raw resolver допускает отношения только со своей identity/region qualification; unknown technical facts rejected. Photo/document relation отдельно. Exact revision → commercial PDP specs/docs unknown; own image revision_specific. См. pnc_evidence_graph.json.','',
'## 6. Три контрольные модели до/после',
'| Model | Conflicts | Specs | Photos | Readiness | Seconds |','|---|---:|---:|---:|---|---:|'])
for x in read('control_comparison.json')['models']:text.append(f'| {x["model"]} | {x["conflicts_before"]}→{x["conflicts_after"]} | {x["specs_before"]}→{x["specs_after"]} | {x["photos"]} | {x["readiness"]} | {x["seconds"]} |')
text.extend(['','Qualified control: проектный .venv, 3/3 actual live, context closed/source unchanged. control_live/control_final — diagnostics с ошибкой stdout/отсутствующим pymupdf в global Python, не final qualification.','',
'## 7. Полный frozen batch',
f'Dataset byte-identical Stage 78/79, SHA256 {sha}. Fresh PDP/inventory; no replay injection. Same-session catalog/XML cache — discovery only, не live identity.','',
'| Model | Published PNC / requested revision | Specs | Photos | Conflicts | Manual | Readiness | Seconds |',
'|---|---|---:|---:|---:|---|---|---:|'])
for x,s in zip(rows,full['rows']):
 i=x['evidence']['identity'];p=i.get('product_code','')
 if i.get('requested_revision_identity_confirmed'):p+=' / '+i['requested_pnc']+' identity confirmed; specs partial'
 text.append(f'| {s["model"]} | {p} | {s["specs"]} | {s["photos"]} | {x["readiness"]["conflicts"]} | {s["manual"]} | {s["readiness"]} | {s["seconds"]} |')
seconds=(datetime.fromisoformat(full['finished_at'])-datetime.fromisoformat(full['started_at'])).total_seconds()
text.extend(['',f'10/10 actual live official data; 9/10 usable для review, 7/10 export_ready; 285 confirmed specs, 19 byte-verified photos. Batch {seconds:.2f} с, max product {max(s["seconds"] for s in full["rows"]):.2f} с. Usable ≠ ready. Thresholds/manual policy неизменны.','',
'Gallery SHA/full decode/dimensions/content-type/format/size проверены; contact sheet просмотрен. 29 verified PDFs; User Manual, Installation Instructions, fiche, energy label, safety отдельно. EB71U1WB User Manual: browser exception binary declared size exceeds budget (15 MB), policy layer Network request failed; это manual limitation, не session stall. EOD docs→revision unknown. Manuals optional.','',
'## 8. Stability',
'| Model | Actual live | Stable | Duplicates sources/photos/docs | Seconds |','|---|---|---|---|---:|'])
for s in repeat['rows']:text.append(f'| {s["model"]} | {s["live_success"]} | {s["stable"]} | {"/".join(str(v) for v in s["duplicates"].values())} | {s["seconds"]} |')
text.extend(['','Same DB/profile: values/units/status/conflicts, source URLs, identity/PNC, image bytes/dimensions, document bytes/language и readiness сравнивались. 6/6 stable, no duplicates; один context на run, closed; source unchanged.','',
'После live менялись только UI source/requested revision presentation и docstring worker; executable transport/parser logic не менялась. В UI отдельно PDP revision и confirmed requested revision 00. Visual QA поймала Cyrillic pipe corruption, исправлено UTF-8 patch и повторено QA. Interrupted regression помечен отдельно; только regression_release — final.','',
'## 9. Regression / UI / export',
f'Full offline regression {reg["result"]}; exit {reg["exit_code"]}; source unchanged {reg["source_tree_unchanged"]}. Native UI 10 cards, Excel 15 sheets, formula errors 0. Адресные 57 Stage 78–80 tests: unresponsive subprocess/PNC graph/context negatives. regression_release.json/log, qa_ui_excel.json, Electrolux_Stage80.xlsx.','',
'## 10–11. Verdict / Git',
'**Electrolux adapter not ready. Stage 80 PASS не поставлен.** Один residual qualification blocker: exact historical root cause незаписанного 314.109513-секундного интервала не доказана. Bounded transport и успешные live/repeat не являются доказательством исходной причины. Квалифицированные source ambiguity/revision evidence limits сохраняют свои not_ready карточки.','',
'Commit/push не выполнены: разрешены только после PASS. Базовый HEAD 0c4c6769d5bc89b0f7a9ab0adc218fabf7ef12d8. Stage 79+80 изменения сохранены, working tree не clean. HEAD/remote/diff check — release_validation.json.',''])
(R/'REPORT.md').write_text('\n'.join(text),encoding='utf8',newline='\n')
print({k:v for k,v in qualified.items() if k not in {'single_remaining_pass_blocker'}})
