"""Audit saved actual worker results; no network, no replay injected into production."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import json,hashlib,collections
from datetime import datetime
from PIL import Image
R=Path(__file__).parent;OLD=R.parent/'dreame_stage76';PHASE='verified_live'
summary=json.loads((R/PHASE/'summary.json').read_text(encoding='utf8'));assert len(summary['first'])==10 and len(summary['second'])==6 and summary['context_closed']
first={};second={};byte_checks=[];proof_checks=[];stability=[]
for passname,destination in [('first',first),('second',second)]:
 for path in (R/PHASE/passname).glob('*/result.json'):
  v=json.loads(path.read_text(encoding='utf8'));destination[v['id']]=v;e=v['evidence']
  assert e['live_success'] and e['observation']=='live_browser' and not e.get('refresh_failed') and v['readiness']['verdict']=='export_ready'
  assert v['readiness']['conflicts']==0 and e['identity']['retail_sku'] is None
  if v['id']==8:
   motor=next(x for x in v['resolved'] if x['normalized_name']=='motor_speed__device');assert (motor['selected_value'],motor['selected_unit'])==('150000','rpm')
  captures=[x for x in e['captures'] if x['url']==e['pdp_url']];assert captures
  for c in e['captures']:
   actual=hashlib.sha256((path.parent/'captures'/c['file']).read_bytes()).hexdigest();assert actual==c['sha256'];proof_checks.append({'pass':passname,'id':v['id'],'file':str(path.parent/'captures'/c['file']),'sha256':actual})
  for m in e.get('image_measurements',[]):
   if not m.get('sha256'):continue
   raw=(path.parent/'captures'/(m['sha256']+'.img')).read_bytes();assert hashlib.sha256(raw).hexdigest()==m['sha256']
   with Image.open(path.parent/'captures'/(m['sha256']+'.img')) as image:image.verify()
   with Image.open(path.parent/'captures'/(m['sha256']+'.img')) as image:image.load();assert image.size==(m['width'],m['height'])
   byte_checks.append({'pass':passname,'id':v['id'],**m,'full_decode_rechecked':True,'bytes_origin':'actual Chrome API response from this worker pass'})
  assert len(e['model_gallery_assets'])==sum(bool(p['selected']) for p in v['photos'])
  assert len({(f['source_key'],f['normalized_name'],f['normalized_value'],f['unit']) for f in v['facts']})==len(v['facts'])
  assert len({(s['source_key'],s['url']) for s in v['sources']})==len(v['sources'])
  assert len({p['url'] for p in v['photos']})==len(v['photos'])
  from product_tool.dreame_page import media_asset_key
  assert len({media_asset_key(p['url']) for p in v['photos']})==len(v['photos'])
  assert len({d['direct_url'] for d in v['documents']})==len(v['documents'])
for ident,b in second.items():
 a=first[ident]
 facts=lambda v:sorted((x['normalized_name'],x['selected_value'],x['selected_unit'],x['status'],x['selected_source'],x['conflict']) for x in v['resolved'])
 sources=lambda v:sorted((x['source_key'],x['url'],x.get('found_model'),x.get('match_level')) for x in v['sources'])
 docs=lambda v:sorted((x['direct_url'],x['language']) for x in v['documents'])
 checks={'sources_equal':sources(a)==sources(b),'facts_equal':facts(a)==facts(b),'photo_assets_equal':a['evidence']['model_gallery_assets']==b['evidence']['model_gallery_assets'],'documents_equal':docs(a)==docs(b),'manual_status_equal':a['readiness']['manual_status']==b['readiness']['manual_status'],'readiness_equal':a['readiness']['verdict']==b['readiness']['verdict'],'actual_live_both':a['evidence']['live_success'] and b['evidence']['live_success']}
 assert all(checks.values()),(ident,checks);stability.append({'id':ident,**checks})
log=json.loads((R/'dreame_fetch_log.json').read_text(encoding='utf8'));prior=json.loads((OLD/'final_live/dreame_fetch_log.json').read_text(encoding='utf8'));assert log[:len(prior)]==prior
new=log[len(prior):];assert not any(x.get('status_code') in (429,401,403) for x in new)
assert not summary['active_stops_after']
manuals=[{'id':i,'status':v['evidence']['manual_status'],'reason':v['evidence'].get('manual_inventory_reason'),'documents':v['documents'],'assessments':v['evidence']['manuals']} for i,v in sorted(first.items())]
metrics={'actual_live_models':len(first),'ready_models':sum(v['readiness']['verdict']=='export_ready' for v in first.values()),'confirmed_specs':sum(v['readiness']['confirmed_specs'] for v in first.values()),'confirmed_photos':sum(len(v['evidence']['model_gallery_assets']) for v in first.values()),'second_actual_live_models':len(second),'new_429':0,'new_http_denials':0,'same_context':True,'contexts':summary['contexts'],'total_navigations':summary['total_navigations'],'source_session':summary['session_id'],'cookies_before_count':summary['cookies_before_count'],'cookies_after_count':summary['cookies_after_count'],'stability':stability,'byte_checks':byte_checks,'dom_proof_checks':proof_checks,'manuals':manuals,'dataset_sha256':summary['dataset_sha256']}
(R/'qualification.json').write_bytes((json.dumps(metrics,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
rows=[]
for ident,v in sorted(first.items()):
 e=v['evidence'];r=v['readiness'];model=v['input']['model'].removeprefix('Dreame ');rows.append(f"| {ident} | {model} | [{e['identity']['source_region']}]({e['pdp_url']}) | {r['confirmed_specs']} | {len(e['model_gallery_assets'])} | {e['manual_status']} | ready | — |")
text=f"""# Stage 77 — Dreame native live qualification

Вердикт ожидает полного regression. Actual live: {metrics['actual_live_models']}/10, ready: {metrics['ready_models']}/10; {metrics['confirmed_specs']} confirmed specs и {metrics['confirmed_photos']} selected byte-verified photos. Frozen Stage 76 dataset SHA256: `{summary['dataset_sha256']}`; dataset не менялся.

## Attended browser
CUA kernel завершался до browser/profile/navigation: `windows sandbox failed: helper_unknown_error: setup refresh had errors` (exit 1). Диагностирован сбой managed Windows sandbox bridge, а не Chrome. Более глубокая причина внутри managed helper не доступна; исправление самого CUA bridge не заявляется. Production recovery использует существующий `PublicBrowserSession`, как предыдущие Razer/HyperX runs: visible persistent Chrome channel `chrome`, executable `C:/Program Files/Google/Chrome/Application/chrome.exe`, version `154.0.8037.98`, dedicated profile `data/dreame_stage77_chrome_profile`, system CA, one context reused across products. Context закрывается в `finally`. Cookies сохраняются между starts; значения cookies/state не экспортируются. Нет stealth, cookie import, CAPTCHA automation или guard reset.

## 429 lifecycle
Все времена UTC 2026-10-10. Global: 22:50:13 → 23:50:13; US: 22:51:55 → 23:51:55; DE: 22:51:57 → 23:51:57. Причина stops: actual HTTP 429 через requests/BinarySafeSession/PolicyAwareSession. Local rate-limit TTL = 1h; scope `domain` означает точный host. Это три независимых stop, а не общий parent-domain stop. Global использовал session `5918bc96a0c04930beba61b4041bad7d`; US/DE `4d5014c92d1b40fd97f3a99d8d9a3dce`. Default HTTP pacing был 1s. Серверная причина назначения 429 сверх наблюдаемого rate limit не установлена.

После stop shared policy отказывает до I/O; `[policy_host_stopped]` — локальный отказ, а не новый server 403. External official-host guard тоже останавливает fallback; он не отключён. Все stops естественно истекли до H14 control (проверка времени 23:52:24 UTC). История сохранена. New visible browser runs: 0 новых 429/401/403. Browser nav pacing = 2s + 1.2s settle; binary GET uses existing host pacing/budgets. Main document ≤3MB, images ≤8MB, documents ≤15MB; 100 nav/30min context bound. Новый 429 останавливает discovery, optional documents, следующие image/dealer requests; PDF/image transport пишет общий Dreame log. Никаких aggressive retry.

## H14 Pro control и native specs
Порядок: ordinary importer → worker.run_once → published catalog href → actual H14 PDP; known PDP URL не seed. Initial live control: exact model, 0 specs/0 photos. Qualified control: 13 specs/3 byte-verified photos, ready; manual advisory. Реальная тема не публиковала Product JSON-LD. SSR `.common-spec-content` содержит `li > span + span`; dirty tank имеет blank-label continuation row. Технические raw section/label/value сохраняются до component/canonical mapping. Другие actual native contracts: `.row-item`, `.spec-content` b/span pairs, semantic `.common-title` sections with span pairs/tables and hidden `show-more-content`. Desktop/mobile одинаковые факты дедуплицируются без подавления разных значений. Dimensions не раскладываются на W/D/H без опубликованного порядка осей.

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
"""+'\n'.join(rows)+f"""

Manual optional. Verified guides: L10s Pro Gen 2 (RU operational pages; generation на отдельной строке обложки), Z30 (EN/RU operational pages), H12 Dual (EN). Языки guide подтверждены operational pages; отдельный Safety PDF не принят вместо User Guide. H12 Dual EN найден по production support index → model detail → published PDF; известный research RU W2221C не инжектирован. L60/H13 checked not found; D30/X50/H14/H15/X40 остались Не проверена из-за технического bounded PDF transport failure, не из-за readiness. Подробные files/language/type/reasons: qualification.json.

## Live / cached / offline / research
Final data — fresh browser PDP navigation + actual HTTP 200 DOM, session `{summary['session_id']}`, {summary['total_navigations']} navigations in one context. Catalog/support navigation cache указан явно как same-session cache; PDP не берётся из capture files. Offline parser tests на saved native HTML/PDF не засчитаны как live success. Research Stage 76 PDF не используется как production discovery seed.

## Gallery aliases / numeric recovery
В visual audit stable_live обнаружены два размера одного Z30 render. Это реальный дубль, хотя URL различны. Common Shopify size-alias normalization сохраняет alias URL, v/revision и crop; final selected asset inventory проверяется по canonical asset key. При raw → normalized проверке также доказано 150,000 RPM → 150 rpm: narrow common normalization теперь читает comma grouping только перед явным RPM, сохраняя decimal commas других величин. Предыдущие batch/regression phases не названы release qualification.

## Stability и выявленный transient bug
До final fix release_live second Z30 получил render_timeout на US, после чего DE documents >6MB не прошли неизменённый 3MB DOM budget. 429 не было. Старый worker уничтожил прежние verified данные. Этот failed run сохранён, не заменён replay-результатами. Исправлено: после DCL timeout можно только заново проверить уже полученный ordinary main 200 DOM через те же challenge/size/status checks, без дополнительной navigation; без200/при guard signal recovery запрещён. Technical unproved refresh той же модели сохраняет source/facts/photos/guides, но маркируется retained_previous_evidence/live_success=false и needs_review. Это не live success и не основание для PASS. Причина самого network/DCL задерживания в старом trace не доказана: main status раньше не записывался; новые failures пишут status/response events.

Final second run: 6/6 actual live — L60, L10s Gen2, H14, Z30, H12 Dual, X40 Master; same context, sources/facts/photo assets/documents/manual statuses/readiness равны first run, duplicates отсутствуют, новый 429 не возник. Числовые comparisons: qualification.json. Metadata-only/captured data не выданы за actual live.

## Regression / UI / Excel / release
Заполняется после final validation. Controlled-use qualification относится к explicit visible persistent Chrome transport; default requests access не объявляется исправленным. Общие identity/thresholds не снижены, отдельный framework не добавлен.
"""
(R/'REPORT.md').write_bytes(text.encode('utf8'))
print({k:metrics[k] for k in ['actual_live_models','ready_models','confirmed_specs','confirmed_photos','second_actual_live_models','new_429','total_navigations']})
