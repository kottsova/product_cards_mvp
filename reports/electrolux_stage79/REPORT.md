# Stage 79 — Electrolux discovery / PNC recovery

**Stage 79 PASS не поставлен:** контрольный audit данных PASS, но один actual live session stall остался без квалифицированного root cause. **Electrolux adapter not ready.** GitHub release не выполнен: пользователь разрешил commit/push после Stage 79 PASS.

## Dataset и границы наблюдений
10 Stage 78 inputs сохранены byte-for-byte, SHA256 `92cc16f718f98b20aafed5a6cc247b72c57fe4b034592078cf0ec58527d69176`. Row 10 по-прежнему synthetic `94949957800`; это не доказанный supplier SKU. `affected_final` — три затронутые модели. `release_live` — новый actual live batch, `release_stability` — шесть fresh повторов в той же DB с persistent profile. Replay не использован ни в одном qualification run. `full_live` — сохранённый failed diagnostic, не successful batch. `affected_live` и `affected_qualified` — промежуточные diagnostics, не release qualification.

## EFI61141B
UK native catalog публикует `EFI61141B → 914932044 → PDP link`, но PDP URL перенаправляет в каталог с обычным 200; PDPContainer отсутствует, reject. Exact Ireland PDP обнаружена из regional official catalog, через опубликованный `/10-kg-washing-machine/efi61141b/` link, без guessed product slug. Ireland отсутствовала в adapter/photo allowlists; UK sitemap раньше расходовал бюджет до other-region phase. Теперь regional catalogs идут до глубоких sitemaps, candidate URLs дедуплицируются.
UK catalog и IE PDP печатают один base PNC; общий route подтверждает product relation. Электрические/regulatory данные Ireland удержаны candidates; региональная эквивалентность не объявлена. Галерея exact model/White byte-verified, supplier finish не придуман. В инструкции проверен EN User Manual. Новый root cause: два различных списка Push Button Functions под одним label/PNC, как у EF7742OBI. Conflict сохранён. Все query/provider/source type/requested/final URLs и accept/reject reasons в row 1 trace.

## EOD6C46K2
PDP не бедная. Frozen input: {'raw': 44, 'accepted_raw': 1, 'rejected_raw': 43, 'confirmed_specs': 1, 'confirmed_photos': 1, 'revision_identity_confirmed': True}. Offline counterfactual **для опубликованного base PNC**, не для synthetic input: {'raw': 44, 'accepted_raw': 34, 'rejected_raw': 10, 'mapped_fields': 38, 'gallery_items': 9}. Native FullSpecification и TopArea gallery доступны; Organization/Product JSON-LD не смешиваются с SSR владельцем. Revision inventory публикует `94949957800` и `94949957801`, но не утверждает общую technical/gallery/document equivalence. Exact requested revision identity подтверждена через observed menu route и native appliance owner. Техническая конфигурация остаётся partial: base-PDP specs/docs не переносятся. Одно фото revision подтверждено relation между own thumbnail и большой published PDP derivative — тот же asset UUID/file, только WS_PV/WS_PN, без crop/query. Миниатюра ниже прежнего size threshold; использован только уже опубликованный большой derivative, URL не сконструирован. Остальные base-PDP images остаются candidates. Raw→accepted→rejected полностью в extraction_audit/result evidence.

## EF7742OBI conflict
Оба ряда относятся к одному PDP/FullSpecification/Other, owner EF7742OBI, PNC `914580516`, revision не напечатана. Первый список: `Delayed Start, ON/OFF, Plus Steam, Prewash, Soft Plus, SPIN SELECTION, Start/Pause, TEMP SELECTION, TIME MANAGER`. Второй: `Cold, Night, NO SPIN, Plus Steam, Prewash, RINSE HOLD, Soft plus, SPEED3, Start/Pause, Temperature 5`. Это не разные revisions и не повтор одинаковой DOM строки. Source label/semantics collision: руководство различает кнопки и опции, второй список также содержит нерасшифрованные служебные названия. Нет оснований объявлять списки эквивалентными или исчерпывающими. Нормализованный конфликт `функции_управления` сохранён; union/rename/first-value selection не применяются. Точные URL/section/row indexes/values — conflict_audit.json; EN control-panel PDF preview — qa.

## PNC / revision
Published numeric product code, nine-digit base и two-digit printed revision сохранены отдельно. PNC не padded. Model inventories разрешают несколько PNC/revisions; весь native modelData.appliances list сохраняется, menu сверяется с payload. Ничего не выбирается первым автоматически. Exact input PNC candidate имеет приоритет перед совпадением только модели; неправильный PNC не прекращает discovery. Adapter выбирает **requested PNC** в опубликованном visible menu, делает fresh GET наблюдённого URL и проверяет unique native appliance owner/code/models. Подчинённые spare-part specs/docs исключены. Live research отдельно проверил `94949957800/01` и `94403205100/01`: routes отвечают 200, native owners содержат code/models/name/image/explodedViewSections; полного appliance spec payload нет. Parts lists revisions различаются. Одинаковые Energylabel-UK-BJB PDF links даже у разных oven models находятся в spare-part grid и не считаются appliance documents. Exact eleven-digit PDP/doc relation имеет приоритет; base-only specs не становятся revision specs после inventory/identity proof. Официальные model URL берутся только из published robots→sitemapindex→Model sitemap links. XML ограничен 3 MB, 14 children, deadline и текущим RequestBudget; incremental same-session catalog cache сохраняет pending children. Native inventory PDP и каждый product PDP открываются свежим navigation. EOF6P46X inventory подтверждает множество base/revisions; это не spec equivalence. См. revision_owner_audit.json.

## HTTP / browser / replay и stability limitation
Default verified requests на UK/IE/shop: ReadTimeout 8 s, **ответ/status не получен**, поэтому 403/429 не приписываются серверу. Visible persistent Chrome с system CA даёт обычные 200. Один context на batch, общий context/cookies для всех товаров, только количество cookies экспортировано. Guards/pacing/cooldowns не сняты: challenge 30 min, rate limit 60 min, HTTP denial 360 min, exact-host scope; manual/fatal independent. Received-main-200 timeout может быть revalidated snapshot без второго navigation, как существующий Dreame flow; challenge/429/foreign redirects остаются stops.

Первый полный attempt `full_live` остановлен через 337 s после старта: последние примерно 314 s trace не менялся после UK catalog→PDP. Сохранены DB/trace/captures и task-process inventory; остановлен только собственный process tree. Один новый actual session retry не использовал replay. В последующих batch stack timer фиксирует обычную работу разных этапов; offline timing XML fingerprint ~0.16 s опроверг предположение, что это постоянный regex hang. Original stalled attempt stack отсутствует; root cause между driver/session/network не доказан. **Не считаем проблему live access полностью закрытой.** Успешные последующие runs показывают работоспособность visible path, а не стирают initial failure. Нового transport/framework не построено.

## До / после
| model | было specs/photos | root cause | PNC/revision | specs | photos confirmed/bytes | conflict | стало |
|---|---:|---|---|---:|---:|---:|---|
| EFI61141B | 0/0 not_ready | UK PDP → catalog redirect; IE absent from allowlist, regional breadth starved; duplicate photo host allowlist; same-PNC source label collision | PDP 914932044 / source revision None / same_product_in_requested_region_catalog | 17 | 2/2 | 1 | not_ready |
| EF7742OBI | 29/2 not_ready | Same owner/section/PNC publishes two unequal Push Button Functions lists; metadata semantics unresolved | PDP 914580516 / source revision None / published_product_confirmed | 29 | 2/2 | 1 | not_ready |
| EDHI618WD | 29/2 export_ready | Stable native PDP; no identity threshold change | PDP 916099992 / source revision None / published_product_confirmed | 29 | 2/2 | 0 | export_ready |
| E52LE100S | 34/2 export_ready | Stable native PDP; no identity threshold change | PDP 911570103 / source revision None / published_product_confirmed | 34 | 2/2 | 0 | export_ready |
| LNT6TE18S5 | 40/2 export_ready | Stable native PDP; no identity threshold change | PDP 925504322 / source revision None / published_product_confirmed | 40 | 2/2 | 0 | export_ready |
| EOF6P46X | 39/2 export_ready | Stable native PDP; no identity threshold change | PDP 944032051 / source revision None / published_product_confirmed | 39 | 2/2 | 0 | export_ready |
| EIV84550 | 27/2 export_ready | Stable native PDP; no identity threshold change | PDP 949599217 / source revision None / published_product_confirmed | 27 | 2/2 | 0 | export_ready |
| EB71U1WB | 39/2 export_ready | Stable native PDP; no identity threshold change | PDP 900258750 / source revision None / published_product_confirmed | 39 | 2/2 | 0 | export_ready |
| EWD746PCBI | 30/2 export_ready | Stable native PDP; no identity threshold change | PDP 914606627 / source revision None / published_product_confirmed | 30 | 2/2 | 0 | export_ready |
| EOD6C46K2 | 1/0 not_ready | Exact revision owner found through published menu; own image linked to larger published derivative; base-PDP technical equivalence unproven | PDP 949499578 / source revision None / base_pnc_partial; exact requested owner 94949957800 confirmed, specs partial | 1 | 1/1 | 0 | not_ready |

Итого actual live official models 10/10, usable evidence для controlled review 9/10, ready 7/10. Usable не равно ready: конфликтные строки требуют review, synthetic revision остаётся partial. False variant facts не добавлены; thresholds/manual policy неизменны.

## Gallery / documents
Byte-verified images 19, confirmed/selected 19; candidate identity отдельно. SHA256/full decode/content type/format/width/height/file size проверены, broken/placeholder не принимаются. См. gallery_audit и contact sheet.
User Manual, Installation Instructions, Product Fiche, Energy Label, Safety отдельно; Installation Manual не становится User Manual. Manuals optional; не входят в readiness blockers.
| model | manual | документы verified/inventory | причина |
|---|---|---:|---|
| EFI61141B | Проверена | 2/4 |  |
| EF7742OBI | Проверена | 4/5 |  |
| EDHI618WD | Проверена | 4/5 |  |
| E52LE100S | Проверена, не найдена | 3/5 | User Manual не опубликован в просмотренной PDP inventory; не заменён fiche/label |
| LNT6TE18S5 | Проверена | 4/6 |  |
| EOF6P46X | Проверена | 4/4 |  |
| EIV84550 | Проверена | 3/4 |  |
| EB71U1WB | Не проверена | 1/2 | Guide URL опубликован, download Network request failed; реальный технический blocker |
| EWD746PCBI | Проверена | 4/5 |  |
| EOD6C46K2 | Не проверена | 0/6 | Revision identity подтверждена; связь базовых документов с revision не доказана |

## Second run
[
  {
    "id": 1,
    "model": "EFI61141B",
    "live_success": true,
    "specs": 17,
    "photos": 2,
    "manual": "Проверена",
    "readiness": "not_ready",
    "stable": true,
    "duplicates": {
      "sources": 0,
      "photos": 0,
      "documents": 0
    },
    "seconds": 64.81
  },
  {
    "id": 3,
    "model": "EDHI618WD",
    "live_success": true,
    "specs": 29,
    "photos": 2,
    "manual": "Проверена",
    "readiness": "export_ready",
    "stable": true,
    "duplicates": {
      "sources": 0,
      "photos": 0,
      "documents": 0
    },
    "seconds": 38.55
  },
  {
    "id": 4,
    "model": "E52LE100S",
    "live_success": true,
    "specs": 34,
    "photos": 2,
    "manual": "Проверена, не найдена",
    "readiness": "export_ready",
    "stable": true,
    "duplicates": {
      "sources": 0,
      "photos": 0,
      "documents": 0
    },
    "seconds": 21.0
  },
  {
    "id": 7,
    "model": "EIV84550",
    "live_success": true,
    "specs": 27,
    "photos": 2,
    "manual": "Проверена",
    "readiness": "export_ready",
    "stable": true,
    "duplicates": {
      "sources": 0,
      "photos": 0,
      "documents": 0
    },
    "seconds": 31.36
  },
  {
    "id": 8,
    "model": "EB71U1WB",
    "live_success": true,
    "specs": 39,
    "photos": 2,
    "manual": "Не проверена",
    "readiness": "export_ready",
    "stable": true,
    "duplicates": {
      "sources": 0,
      "photos": 0,
      "documents": 0
    },
    "seconds": 55.41
  },
  {
    "id": 10,
    "model": "EOD6C46K2",
    "live_success": true,
    "specs": 1,
    "photos": 1,
    "manual": "Не проверена",
    "readiness": "not_ready",
    "stable": true,
    "duplicates": {
      "sources": 0,
      "photos": 0,
      "documents": 0
    },
    "seconds": 27.7
  }
]
Повтор в той же DB: source URLs, normalized values/units/status/conflicts, gallery bytes/selection, document bytes/language, PNC relation и readiness сравниваются; counts дубликатов source/photo/document = 0 при успешном результате. Один persistent profile, один context этого run; context закрыт штатно.

## Regression / verdict / Git
Полный offline regression: ['Ran 1868 tests in 257.783s', 'OK'], exit=0, source tree unchanged=True. Адресные тесты включают exact-PNC ordering, inventory owner/menu match, negative revision/color/region transfer и lookalike image hosts. Native UI/Excel QA отдельна от actual live.
**Electrolux adapter not ready**: unresolved initial driver/session stall, same-PNC source label collisions EFI61141B/EF7742OBI, EOD6C46K2 exact-revision technical equivalence отсутствует; default HTTP не квалифицирован. Stage 79 PASS не поставлен, commit/push не выполнены. Базовый HEAD `0c4c6769d5bc89b0f7a9ab0adc218fabf7ef12d8`; изменения и проверяемые artifacts сохранены в working tree.
