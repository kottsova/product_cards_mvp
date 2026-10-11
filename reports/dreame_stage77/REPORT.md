# Stage 77 — Dreame native live qualification

Stage 77 **PASS**. **Dreame adapter production-ready for controlled use** через explicit visible persistent Chrome transport. Actual live: 10/10, ready: 10/10; 134 confirmed specs и 16 selected byte-verified photos. Frozen Stage 76 dataset SHA256: `7872d84dabdda9b716cd594276273b5560832b2720709cb6610ed1ecbb521afd`; dataset не менялся.

## Attended browser
CUA kernel завершался до browser/profile/navigation: `windows sandbox failed: helper_unknown_error: setup refresh had errors` (exit 1). Диагностирован сбой managed Windows sandbox bridge, а не Chrome. Более глубокая причина внутри managed helper не доступна; исправление самого CUA bridge не заявляется. Production recovery использует существующий `PublicBrowserSession`, как предыдущие Razer/HyperX runs: visible persistent Chrome channel `chrome`, executable `C:/Program Files/Google/Chrome/Application/chrome.exe`, version `154.0.8037.98`, dedicated profile `data/dreame_stage77_chrome_profile`, system CA, one context reused across products. Context закрывается в `finally`. Cookies сохраняются между starts; значения cookies/state не экспортируются. Нет stealth, cookie import, CAPTCHA automation или guard reset.

## 429 lifecycle
Все времена UTC 2026-10-10. Global: 22:50:13 → 23:50:13; US: 22:51:55 → 23:51:55; DE: 22:51:57 → 23:51:57. Причина stops: actual HTTP 429 через requests/BinarySafeSession/PolicyAwareSession. Local rate-limit TTL = 1h; scope `domain` означает точный host. Это три независимых stop, а не общий parent-domain stop. Global использовал session `5918bc96a0c04930beba61b4041bad7d`; US/DE `4d5014c92d1b40fd97f3a99d8d9a3dce`. Default HTTP pacing был 1s. Серверная причина назначения 429 сверх наблюдаемого rate limit не установлена.

После stop shared policy отказывает до I/O; `[policy_host_stopped]` — локальный отказ, а не новый server 403. External official-host guard тоже останавливает fallback; он не отключён. Все stops естественно истекли до H14 control (проверка времени 23:52:24 UTC). История сохранена. New visible browser runs: 0 новых 429/401/403. Browser nav pacing = 2s + 1.2s settle; binary GET uses existing host pacing/budgets. Main document ≤3MB, images ≤8MB, documents ≤15MB; 100 nav/30min context bound. Новый 429 останавливает discovery, optional documents, следующие image/dealer requests; PDF/image transport пишет общий Dreame log. Никаких aggressive retry.

## H14 Pro control и native specs
Порядок: ordinary importer → worker.run_once → published catalog href → actual H14 PDP; known PDP URL не seed. Initial live control: exact model, 0 specs/0 photos. Qualified control: 13 specs/3 byte-verified photos, ready; manual advisory. Реальная тема не публиковала Product JSON-LD. SSR `.common-spec-content` содержит `li > span + span`; dirty tank имеет blank-label continuation row. Технические raw section/label/value сохраняются до component/canonical mapping. Initial capture filename содержал hash DOM string; старый Windows text writer менял LF на CRLF (actual raw SHA a33dd6a6… вместо d06ce92b…). Writer исправлен на UTF-8 bytes; все final capture raw SHA повторно сверены с proof SHA. Initial native fixture отдельно закрепляет её реальный byte hash. Другие actual native contracts: `.row-item`, `.spec-content` b/span pairs, semantic `.common-title` sections with span pairs/tables and hidden `show-more-content`. Desktop/mobile одинаковые факты дедуплицируются без подавления разных значений. Dimensions не раскладываются на W/D/H без опубликованного порядка осей.

| Проверено для H14 | Техническое evidence / решение |
|---|---|
| suction | H2 `Uncompromised 18kPa Suction`; marketing heading отдельно, не перенесён в tech table facts |
| runtime | Maximum Runtime → 40min |
| battery | Battery Capacity → 6 x 5,000mAh; не превращено в сумму ёмкостей |
| clean-water tank | Clean Water Tank → 880mL |
| dirty-water tank | Used Water Tank → Standing 650mL / Lie-Flat 450mL |
| self-cleaning / hot-water cleaning | native feature headings, включая 140°F (60°C); отдельно от technical specs |
| drying | Hot Air Drying → 5min (Super-Speed)/1hr (Quiet) |
| lie-flat | 180° Lie-Flat Reach H2; feature heading отдельно |
| edge cleaning | Brush Type → Dual Edge Cleaning |
| dimensions | В проверенной H14 technical table не опубликованы; не выдуманы |
| weight | Weight → 12.57 lbs (5.7kg); normalization 5.7kg |

## Native gallery и scope
Hero H14 — video, не image. Product gallery recovery берёт multiple `og:image:secure_url` только при согласованных exact model title/type/current URL. Exact-labelled device item render в package block допустим как model render; standalone accessory/package inventory остаётся candidate. Published model gallery может содержать композицию Complete bundle и component diagram; это не подтверждает supplier bundle/color или технический факт. Content roles каждого выбранного изображения отдельно описаны в gallery_visual_review.json. Feature icons и остальные изображения вне опубликованной gallery не подставлены как gallery. Shopify resize aliases дедуплицируются с сохранением alias URL; revision/crop не объединяются. `no-image` placeholders исключены. Для всех confirmed photos проверены MIME, full PIL verify/load, dimensions, size, actual format, SHA256; audit повторно проверил те же сохранённые live bytes без новой сети. Supplier color не заявляется. 380px H14 package render отклонён текущей dimensions policy; thresholds не снижались. Filename extension не определяет format.

Model identity сохраняет строгие Pro/Gen/Dual/Heat/Slim distinctions. Slogan/empty H1 допускает согласованные document title + og:title + og:url; явная другая модель в H1 имеет приоритет. Global `/z30` показывает Z30 Slim и отклонён; exact Z30 найден через published US catalog. Robot/station dimensions/weight разделены по печатным component headings; ambiguous Clean/Waste tank остаётся candidate. Hidden X40 Auto Dust Collection power 1,000W и bag 4.2L относятся к station, не robot. Optional TriCut purchased-separately row не подтверждён как стандартный комплект.

## Final actual live batch
| ID | model | official PDP | live specs | confirmed photos | manual | readiness | blocker |
|---|---|---|---:|---:|---|---|---|
| 1 | L60 Ultra | [Global](https://global.dreametech.com/products/l60-ultra) | 24 | 1 | Проверена, не найдена | ready | — |
| 2 | L10s Pro Gen 2 | [Global](https://global.dreametech.com/products/l10s-pro-gen-2) | 12 | 1 | Проверена | ready | — |
| 3 | D30 Ultra | [Global](https://global.dreametech.com/products/d30-ultra) | 12 | 1 | Не проверена | ready | — |
| 4 | X50 Ultra | [Global](https://global.dreametech.com/products/dreame-x50-ultra-complete) | 4 | 3 | Не проверена | ready | — |
| 5 | H14 Pro | [Global](https://global.dreametech.com/products/h14-pro) | 13 | 3 | Не проверена | ready | — |
| 6 | H13 Pro | [Global](https://global.dreametech.com/products/h13-pro) | 14 | 1 | Проверена, не найдена | ready | — |
| 7 | H15 Pro Heat | [Global](https://global.dreametech.com/products/dreame-h15-pro-heat) | 12 | 1 | Не проверена | ready | — |
| 8 | Z30 | [US](https://www.dreametech.com/products/z30-cordless-stick-vacuum) | 8 | 3 | Проверена | ready | — |
| 9 | H12 Dual | [Global](https://global.dreametech.com/products/h12-dual) | 16 | 1 | Проверена | ready | — |
| 10 | X40 Master | [Global](https://global.dreametech.com/products/x40-master) | 19 | 1 | Не проверена | ready | — |

Manual optional. Verified guides: L10s Pro Gen 2 (RU operational pages; generation на отдельной строке обложки), Z30 (EN/RU operational pages), H12 Dual (EN). Языки guide подтверждены operational pages; отдельный Safety PDF не принят вместо User Guide. H12 Dual EN найден по production support index → model detail → published PDF; известный research RU W2221C не инжектирован. L60/H13 checked not found; D30/X50/H14/H15/X40 остались Не проверена из-за технического bounded PDF transport failure, не из-за readiness. Подробные files/language/type/reasons: qualification.json.

## Live / cached / offline / research
Final data — fresh browser PDP navigation + actual HTTP 200 DOM, session `public_browser:a0d1074014124547a38b664d3e2f7185`, 35 navigations in one context. Catalog/support navigation cache указан явно как same-session cache; PDP не берётся из capture files. Offline parser tests на saved native HTML/PDF не засчитаны как live success. Research Stage 76 PDF не используется как production discovery seed.

## Gallery aliases / numeric recovery
В visual audit stable_live обнаружены два размера одного Z30 render. Это реальный дубль, хотя URL различны. Common Shopify size-alias normalization сохраняет alias URL, v/revision и crop; final selected asset inventory проверяется по canonical asset key. При raw → normalized проверке также доказано 150,000 RPM → 150 rpm: narrow common normalization теперь читает comma grouping только перед явным RPM, сохраняя decimal commas других величин. Предыдущие batch/regression phases не названы release qualification.

## Stability и выявленный transient bug
До final fix release_live second Z30 получил render_timeout на US, после чего DE documents >6MB не прошли неизменённый 3MB DOM budget. 429 не было. Старый worker уничтожил прежние verified данные. Этот failed run сохранён, не заменён replay-результатами. Исправлено: после DCL timeout можно только заново проверить уже полученный ordinary main 200 DOM через те же challenge/size/status checks, без дополнительной navigation; без200/при guard signal recovery запрещён. Technical unproved refresh той же модели сохраняет source/facts/photos/guides, но маркируется retained_previous_evidence/live_success=false и needs_review. Это не live success и не основание для PASS. Причина самого network/DCL задерживания в старом trace не доказана: main status раньше не записывался; новые failures пишут status/response events.

Final second run: 6/6 actual live — L60, L10s Gen2, H14, Z30, H12 Dual, X40 Master; same context, sources/facts/photo assets/documents/manual statuses/readiness равны first run, duplicates отсутствуют, новый 429 не возник. Числовые comparisons: qualification.json. Metadata-only/captured data не выданы за actual live.

## Regression / UI / Excel / release
Полный `.venv/Scripts/python.exe -X utf8 -m tests`: **1817 tests / OK**, 709.560s (runner 713.218s), network guard включён, source manifest до/после равен; 30 новых Stage 77 cases. Нативные UI 10/10 и Excel exporter прошли; пять карточек × три screenshot views, selected images реально декодированы и показаны из saved live bytes, input configuration отделена от official facts, formula errors = 0. В read-only artifact-tool QA созданы и визуально проверены три PNG, после чего вспомогательный renderer завершился exit 1 без error text; это не названо успешным renderer run. Сам native XLSX независимо проверен openpyxl. `git diff --check` пройден перед release; staged check выполняется перед commit.

Controlled-use qualification относится к explicit visible persistent Chrome transport, same profile/context, bounded budgets и действующему access guard. Default requests access не объявляется исправленным; managed CUA bridge остаётся отдельной инфраструктурной неисправностью. Все final actual results — verified_live; прежние phases и cancelled regressions сохранены как диагностические evidence и не используются для release verdict. Общие identity/thresholds не снижены, отдельный framework не добавлен. Manual optional; технически недоступные PDF не названы отсутствующими.

Public artifact inventory и SHA: evidence_manifest.json; SQLite, inputs, browser profile и cookie/state values не публикуются. Commit hash / HEAD==origin/main / clean working tree подтверждаются после push в финальном ответе.
