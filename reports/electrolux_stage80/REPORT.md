# Stage 80 — Electrolux final blockers

**Stage 80 PASS не поставлен. Electrolux adapter not ready.**

Единственный остаточный блокер qualification: точная причина исторического 337-second stall не доказана. Дефект ограничений runtime исправлен, новые actual live запуски стабильны; это не восстанавливает отсутствующий historical stack. Конфликты производителя и revision specs gap квалифицированы и сохранены в карточках.

## 1. Session stall / timing / budgets
Исходный запуск: 337.109513 с; завершённые discovery events занимают 23 с, затем 314.109513 с без trace. Последний URL — UK washing-machine catalog, перед следующим PDP candidate. Нет start-event navigation, DOM/snapshot-start или исходного stack. Нельзя доказать, что ожидал goto, DOM, driver или иной синхронный вызов. Job уже был claimed; docs/photos не достигнуты в последнем зафиксированном маршруте. Нет evidence для queue/retry/backoff/networkidle cause.

Offline catalog/protection parse всех четырёх historical captures — вместе менее 0.12 с. Это counterfactual parser timing, не доказательство исходной причины и не live success.

Доказанный дефект: прямой синхронный PublicBrowserSession ограничивал goto, но не весь driver/snapshot/binary call. Existing PlaywrightBrowser worker protocol расширен opt-in guarded public commands. Один worker/context на run, dedicated visible persistent Chrome profile, system CA; access-stop/challenge/429 guards сохранены. Внешний wall wait прекращает только owned worker tree. Техническое восстановление максимум одно, для следующего товара; host stops не снимаются. CAPTCHA не обходится, cookies values не импортируются/экспортируются.

Budgets: native navigation 10 с (не увеличен), navigation driver wall 18 с, snapshot wall 6 с; candidate 24 с, discovery 100 с, product 150 с, document fetch 12 с / batch 35 с, image batch 24 с. Driver wall bound — принудительный; stage/product deadline проверяется между ограниченными операциями. Parse/decode/persistence имеют byte/page/DOM caps; hard CPU preemption не заявляется.

Trace: job start → discovery → candidate/navigation → DOM ready → extraction → documents → photos → persistence → job finish. Navigation: URL, start/end, wall timeout, elapsed, native events/status/redirect, exception, challenge, retries. Networkidle не используется. См. timing_analysis.json и browser_timing.jsonl каждого run. Fault injection с не отвечающим subprocess подтверждает остановку caller wait, не воспроизводит historical cause.

## 2–3. EFI61141B / EF7742OBI conflicts
Обе пары находятся в единственном native FullSpecification, одном parent Other. Rows содержат label/infoText, без различающих semantic key/attribute ID. Summary повторяет первый список; extractor читает только FullSpecification, не объединяет summary с полной таблицей. Разные позиции массива не доказывают разные понятия. Manual различает кнопки/опции, но не квалифицирует второй исчерпывающий список/internal codes. Canonical split по интерпретации слов не выполнен; source ambiguity и needs_review сохранены.

### EFI61141B
Source: https://www.electrolux.ie/laundry/laundry/washing-machines/front-loader-washing-machine/efi61141b/; native PNC 914932044; revision не напечатана. Classification: native duplicate-label ambiguity; conflict retained.
- Section: Other; raw label: Push Button Functions.
  Raw value: DELAY, ON/OFF, Prewash, SPIN SELECTION, Start/Pause, TEMP SELECTION, TIME MANAGER.
  Structured path: $.props.pageProps.pageData.components[1].components[2].components[2].props.attributes[3].items[1].
- Section: Other; raw label: Push Button Functions.
  Raw value: Delay, Extra rinse, Prewash, RINSE HOLD, Silent, Start/Pause, Time manager.
  Structured path: $.props.pageProps.pageData.components[1].components[2].components[2].props.attributes[3].items[7].

### EF7742OBI
Source: https://www.electrolux.co.uk/laundry/laundry/washing-machines/built-in-washing-machine/ef7742obi/; native PNC 914580516; revision не напечатана. Classification: native duplicate-label ambiguity; conflict retained.
- Section: Other; raw label: Push Button Functions.
  Raw value: Delayed Start, ON/OFF, Plus Steam, Prewash, Soft Plus, SPIN SELECTION, Start/Pause, TEMP SELECTION, TIME MANAGER.
  Structured path: $.props.pageProps.pageData.components[1].components[3].components[3].props.attributes[4].items[1].
- Section: Other; raw label: Push Button Functions.
  Raw value: Cold, Night, NO SPIN, Plus Steam, Prewash, RINSE HOLD, Soft plus, SPEED3, Start/Pause, Temperature 5.
  Structured path: $.props.pageProps.pageData.components[1].components[3].components[3].props.attributes[4].items[6].

## 4. EOD6C46K2 / 94949957800 rejects
Exact revision owner подтверждён fresh menu navigation и native appliance object. Inventory публикует 94949957800/01. Owner.models содержит только code EOD6C46K2; ссылка возвращает shop model inventory. Owner/modelData не публикуют direct commercial PDP technical relation. Exploded views принадлежат requested revision; subordinate part facts/docs исключены.

Commercial PDP печатает base PNC 949499578: 44 raw → 1 accepted / 43 rejected. 33 structured technical fields имеют unknown relation к requested revision; 10 — marketing/malformed prose. Каждое rejected field: source identity, relation, raw value/path, reason — revision_reject_analysis.json. Dimensions/power/capacity/programmes/configuration не перенесены. Отдельный base-PNC offline parser result Stage 79 — 38 mapped specs; это не frozen-input revision success.

Дополнительный actual live fetch: Specification Sheet, User Manual, Energy Label и Product Fiche получены и прочитаны как candidates. Все четыре печатают только base PNC 949499578; full 94949957800/01 отсутствуют. Они не создают revision→technical PDP relation. См. revision_document_research.json и PDF/text artifacts. Эти четыре byte-verified PDF не добавлены к 29 identity-qualified documents карточек.

Photo: exact appliance.image и опубликованный larger PDP derivative имеют один UUID/file. Одно подтверждённое 700×700 изображение; equivalence только image, не specs/finish/docs. Thumbnail не увеличивался искусственно. Synthetic input не изменён; technical configuration partial.

## 5. PNC evidence graph
model → published inventory → exact PNC/revision → evidence. Типы exact_pnc, model_shared, revision_specific, unknown. Все PNC сохраняются, первый не выбирается, padding нет. Raw resolver допускает отношения только со своей identity/region qualification; unknown technical facts rejected. Photo/document relation отдельно. Exact revision → commercial PDP specs/docs unknown; own image revision_specific. См. pnc_evidence_graph.json.

## 6. Три контрольные модели до/после
| Model | Conflicts | Specs | Photos | Readiness | Seconds |
|---|---:|---:|---:|---|---:|
| EFI61141B | 1→1 | 17→17 | 2 | not_ready | 65.6 |
| EF7742OBI | 1→1 | 29→29 | 2 | not_ready | 50.75 |
| EOD6C46K2 | 0→0 | 1→1 | 1 | not_ready | 27.39 |

Qualified control: проектный .venv, 3/3 actual live, context closed/source unchanged. control_live/control_final — diagnostics с ошибкой stdout/отсутствующим pymupdf в global Python, не final qualification.

## 7. Полный frozen batch
Dataset byte-identical Stage 78/79, SHA256 92cc16f718f98b20aafed5a6cc247b72c57fe4b034592078cf0ec58527d69176. Fresh PDP/inventory; no replay injection. Same-session catalog/XML cache — discovery only, не live identity.

| Model | Published PNC / requested revision | Specs | Photos | Conflicts | Manual | Readiness | Seconds |
|---|---|---:|---:|---:|---|---|---:|
| EFI61141B | 914932044 | 17 | 2 | 1 | Проверена | not_ready | 65.53 |
| EF7742OBI | 914580516 | 29 | 2 | 1 | Проверена | not_ready | 50.34 |
| EDHI618WD | 916099992 | 29 | 2 | 0 | Проверена | export_ready | 24.34 |
| E52LE100S | 911570103 | 34 | 2 | 0 | Проверена, не найдена | export_ready | 21.23 |
| LNT6TE18S5 | 925504322 | 40 | 2 | 0 | Проверена | export_ready | 22.42 |
| EOF6P46X | 944032051 | 39 | 2 | 0 | Проверена | export_ready | 24.49 |
| EIV84550 | 949599217 | 27 | 2 | 0 | Проверена | export_ready | 18.65 |
| EB71U1WB | 900258750 | 39 | 2 | 0 | Не проверена | export_ready | 59.43 |
| EWD746PCBI | 914606627 | 30 | 2 | 0 | Проверена | export_ready | 23.74 |
| EOD6C46K2 | 949499578 / 94949957800 identity confirmed; specs partial | 1 | 1 | 0 | Не проверена | not_ready | 28.98 |

10/10 actual live official data; 9/10 usable для review, 7/10 export_ready; 285 confirmed specs, 19 byte-verified photos. Batch 340.26 с, max product 65.53 с. Usable ≠ ready. Thresholds/manual policy неизменны.

Gallery SHA/full decode/dimensions/content-type/format/size проверены; contact sheet просмотрен. 29 verified PDFs; User Manual, Installation Instructions, fiche, energy label, safety отдельно. EB71U1WB User Manual: browser exception binary declared size exceeds budget (15 MB), policy layer Network request failed; это manual limitation, не session stall. EOD docs→revision unknown. Manuals optional.

## 8. Stability
| Model | Actual live | Stable | Duplicates sources/photos/docs | Seconds |
|---|---|---|---|---:|
| EFI61141B | True | True | 0/0/0 | 65.74 |
| EDHI618WD | True | True | 0/0/0 | 39.55 |
| E52LE100S | True | True | 0/0/0 | 22.06 |
| EIV84550 | True | True | 0/0/0 | 31.42 |
| EB71U1WB | True | True | 0/0/0 | 53.01 |
| EOD6C46K2 | True | True | 0/0/0 | 29.19 |

Same DB/profile: values/units/status/conflicts, source URLs, identity/PNC, image bytes/dimensions, document bytes/language и readiness сравнивались. 6/6 stable, no duplicates; один context на run, closed; source unchanged.

После live менялись только UI source/requested revision presentation и docstring worker; executable transport/parser logic не менялась. В UI отдельно PDP revision и confirmed requested revision 00. Visual QA поймала Cyrillic pipe corruption, исправлено UTF-8 patch и повторено QA. Interrupted regression помечен отдельно; только regression_release — final.

## 9. Regression / UI / export
Full offline regression ['Ran 1874 tests in 234.102s', 'OK']; exit 0; source unchanged True. Native UI 10 cards, Excel 15 sheets, formula errors 0. Адресные 57 Stage 78–80 tests: unresponsive subprocess/PNC graph/context negatives. regression_release.json/log, qa_ui_excel.json, Electrolux_Stage80.xlsx.

## 10–11. Verdict / Git
**Electrolux adapter not ready. Stage 80 PASS не поставлен.** Один residual qualification blocker: exact historical root cause незаписанного 314.109513-секундного интервала не доказана. Bounded transport и успешные live/repeat не являются доказательством исходной причины. Квалифицированные source ambiguity/revision evidence limits сохраняют свои not_ready карточки.

Commit/push не выполнены: разрешены только после PASS. Базовый HEAD 0c4c6769d5bc89b0f7a9ab0adc218fabf7ef12d8. Stage 79+80 изменения сохранены, working tree не clean. HEAD/remote/diff check — release_validation.json.
