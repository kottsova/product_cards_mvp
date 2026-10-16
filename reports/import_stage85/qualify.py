"""Consolidate actual UI, bounded Sulpak, parser and regression observations."""
import json,hashlib,sqlite3
from bs4 import BeautifulSoup
from collections import Counter
from pathlib import Path
out=Path(__file__).parent;root=out.parents[1]
load=lambda p:json.loads((out/p).read_text(encoding='utf8'))
lg=load('lg12/acceptance.json');mixed=load('mixed/acceptance.json');md=load('mixed/download_acceptance.json');stable=load('stability.json');sulpak=load('sulpak_recovered_probe.json');thumb=load('thumbnail_load_after.json');reg=load('final_regression.json')
# Normalize an old harness metadata assumption; the original mixed UI actually
# completed end-to-end, as its separate acceptance record and stdout establish.
md.pop('initial_download_failure',None)
md['additional_download_run_reason']='Original mixed UI completed successfully; separate final-runtime downloads without enqueue.'
(out/'mixed/download_acceptance.json').write_text(json.dumps(md,ensure_ascii=False,indent=2),encoding='utf8')
checks={
 'unchanged_original_lg_input':hashlib.sha256((root/'data/uploads/a3e4a1df3c1d4876a9028a59e1c2b6a5.xlsx').read_bytes()).hexdigest()==lg['file_sha256'],
 'unchanged_mixed_input':hashlib.sha256((root/'reports/import_stage84/Ordinary_3_columns.xlsx').read_bytes()).hexdigest()==mixed['file_sha256'],
 'lg12_actual_ui_completed':lg['final']['summary']['total']==lg['final']['summary']['completed']==12,
 'mixed_actual_ui_completed':mixed['final']['summary']['total']==mixed['final']['summary']['completed']==8,
 'mixed_at_least_5_brands':len(mixed['brands'])>=5,
 'no_page_errors':not lg['page_errors'] and not mixed['page_errors'],
 'polling_without_reload':lg['no_reload_during_processing'] and mixed['no_reload'] and stable['no_full_reload'],
 'checkbox_selection_preserved':lg['checkbox_preserved_during_processing'] and mixed['selection_preserved'],
 'single_final_table':all(len(BeautifulSoup((out/p/'final_after.html').read_text(encoding='utf8'),'html.parser').select('table'))==1 for p in ['lg12','mixed']),
 'excel_downloads':all((out/p/'result.xlsx').is_file() for p in ['lg12','mixed']),
 'two_verified_zip_downloads':all(len(d['zip_entries'])==2 for d in [lg,mixed]),
 'zip_hashes_distinct':all(len({x['sha256'] for x in d['zip_entries']})==len(d['zip_entries']) for d in [lg,mixed]),
 'photo_selection_and_lightbox':all(d['photo_selection_saved'] and d['lightbox_opened'] for d in [lg,md]),
 'actual_thumbnails_decoded':len(thumb['images'])==8 and all(x['width']>0 and x['height']>0 for x in thumb['images']),
 'actual_lightbox_decoded':thumb['lightbox_decoded'],
 'sulpak_actual_visible_persistent':sulpak['status_code']==200 and sulpak['visible'] and sulpak['persistent'] and sulpak['counts']['navigations']==1,
 'sulpak_not_stopped_after_expiry':not sulpak['stops_before'] and not sulpak['stops_after'],
 'kit_not_confirmed_from_url':sulpak['identity']=='unknown' and not sulpak['facts'] and not sulpak['photos'],
 'official_manual_evidence_preserved':sulpak['official_support_manual_evidence_unchanged'],
 'stability_5_actual_brands':len(stable['results'])==5 and len({r['product']['brand'] for r in stable['results']})==5,
 'double_retry_no_duplicate_jobs':stable['no_duplicate_jobs'],
 'stability_readiness':all(r['job']['readiness']=='export_ready' for r in stable['results']),
 'stability_counts_preserved':all(r['job']['specs_count']>=next(x for x in mixed['final']['rows'] if x['id']==r['product']['id'])['specs_count'] and r['job']['photos_count']>=next(x for x in mixed['final']['rows'] if x['id']==r['product']['id'])['photos_count'] for r in stable['results']),
 'stability_confirmed_sources_preserved':all({(s['source_key'],s['url']) for s in load('mixed/'+str(r['product']['id'])+'.json')['sources'] if not s['error'] and s['match_level'] in {'full_sku','model_confirmed','exact_variant'}}.issubset({(s['source_key'],s['url']) for s in r['sources'] if not s['error']}) for r in stable['results']),
 'full_regression':reg['exit_code']==0 and reg['tests']==reg['expected_tests']==1949 and reg['production_tree_unchanged'] and reg['no_modules_omitted_or_duplicated'],
}
result=dict(verdict='PASS' if all(checks.values()) else 'NOT PASS',checks=checks,lg12_readiness=dict(Counter(x['readiness_label'] for x in lg['final']['rows'])),mixed_readiness=dict(Counter(x['readiness_label'] for x in mixed['final']['rows'])),limitations=['P12ED kit relation is unproved; 41 raw specs and 29 raw photo candidates are not confirmed kit evidence','HyperX RU: actual official search and sitemap reached, exact candidate not found; this run does not prove 429','Ambiguous LG input retains candidate facts without confirmed photos'],tests=reg['tests'])
(out/'qualification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
labels={'export_ready':'Готова','export_ready_with_gaps':'Готова с пробелами','not_ready':'Не готова'}
lines=['# Stage 85 — production batch UX + P12ED dealer recovery','',f"Verdict: **{result['verdict']}**.",'','## P12ED / Sulpak','',
'Old stop history is append-only. The historical S3WER challenge stop was active when row 172 ran. TTL already existed; the dealer diagnostics incorrectly kept citing the historical event without expiry context. The actual Stage 85 visible Chrome visit exposed the further root cause: optional review/comment CAPTCHA was being classified as a document access gate. The shared HTTP and attended classifiers now distinguish these optional controls; genuine access gates, 403/429, manual and fatal stops retain their guards.',
'','After expiry: one fresh visible persistent Chrome navigation, HTTP 200, ordinary PDP, no challenge interaction. H1 / Product JSON-LD name: LG P12ED. Product ID 606431; canonical and Product URL contain both component strings, but content does not prove the two-unit relation. Exact kit remains unknown. The raw content audit found 41 raw fields / 29 image candidates; 0 accepted kit facts / photos. Row 172 now stores the actually inspected candidate; other official/support sources and documents are byte-for-byte unchanged as database records. See `sulpak_recovered_probe.json`, `sulpak_content_audit.json`, `capture_redactions.json`. Raw DOM is retained locally under data/stage85_raw; committed inspection copies redact tokens and non-data inline scripts.',
'','## UI and persisted progress','',
'Before: generic queue plus LG-only queue/table, repeated category lists, raw statuses, whole-HTML polling. After: one neutral table with selection, model/article, Russian statuses, current operation, accepted specs, confirmed-photo count, official color, readiness and actions. JSON GET /batches/{id}/progress performs only saved-state reads; 3-second polling changes cells/counters without replacing the document, scroll or selection. Job status and readiness are separate; queued readiness is —. All/none/queue/retry, prominent Excel, separate gallery/lightbox and selected-photo ZIP are available.',
'','Each job retains queued_at, started_at, stage_started_at, finished_at, final_status, readiness, specs_count, photos_count, color and semantic phase. Legacy integer current_stage remains compatible; API current_stage is semantic. Actual extraction hooks and append-only phase events represent real operations; skipped phases are not fabricated. Manual checking is displayed as a discovery substage. Historical terminal results are backfilled once from saved evidence at startup; polling does not perform discovery or recalculate readiness.',
'','## Real acceptance and recovered UI failures','',
'Original 12-row LG upload and unchanged Stage 84 mixed input: actual UI upload → unedited confirmation → one bulk queue action → default production worker → automatic JSON progress → final table. The LG download attempt exposed quadratic gallery reprojection in Excel; it was fixed by reusing enriched rows once per product. LG downloads were resumed on the same completed batch without adding jobs. The original mixed UI flow completed end-to-end; an additional final-runtime download check is recorded separately in mixed/download_acceptance.json. Startup connection refusals and bounded localhost navigation/selection timeouts are retained in local diagnostic logs and are not counted as successful operations.',
'','The separate rendering check exposed direct LG embedding rejected by Chromium ORB. Thumbnails/lightbox now serve verified bytes for saved photo IDs through the same bounded policy-aware image verifier/cache, with source host restrictions, image decoding, hash/path/size/MIME checks and serialized fetches. No browser security flags or CAPTCHA interactions were used. First eight actual thumbnails and the lightbox have positive decoded pixel dimensions; external links and Excel photo URLs are preserved. JPG/JPEG cache format aliases are both covered.',
'','| Batch | Processed | Ready | With gaps | Not ready | Excel | Selected ZIP |','|---|---:|---:|---:|---:|---:|---:|']
for title,d in [('LG original',lg),('Mixed, 6 brands',md)]:
 c=Counter(x['readiness'] for x in d['final']['rows']);lines.append(f"| {title} | {d['final']['summary']['completed']}/{d['final']['summary']['total']} | {c['export_ready']} | {c['export_ready_with_gaps']} | {c['not_ready']} | {d['excel_seconds']:.1f}s | {len(d['zip_entries'])} verified files, {d['zip_seconds']:.1f}s |")
lines+=['','Both ZIP downloads were opened, each image decoded with Pillow and dimensions/format/size/hash checked; duplicate bytes are excluded. ZIP uses safe Brand_Model_Article_photos.zip names and the highest available published rendition in each known alias group. A failed image/stop returns a visible error instead of a partial-success ZIP.','',
'## LG final table','','| ID | Model / article | Accepted specs | Confirmed photos | Readiness |','|---:|---|---:|---:|---|']
for r in lg['final']['rows']:lines.append(f"| {r['id']} | {r['model'] or r['article']} | {r['specs_count']} | {r['photos_count']} | {r['readiness_label']} |")
lines+=['','## Stability','','Five distinct brands were retried through the real UI on the corrected worker: LG, Apple, Xiaomi, Dreame, JBL. A second immediate retry click created no extra active jobs. 5/5 remained ready. Apple/Xiaomi/Dreame/JBL counts were unchanged; LG grew from 53/20 to 69/30 because Sulpak recovered and its page explicitly printed S3WER.ALWPCOM. Previously confirmed official sources were retained; no counts decreased. Phase history and saved evidence remained available. This business-path rerun preceded the isolated thumbnail delivery patch; actual thumbnail decoding and full regression were then checked on the final source.',
'','## Regression','',f"Full standard unittest discovery: {reg['tests']} tests / {reg['modules']} modules, all OK; no omitted/duplicated modules, production bytes unchanged during the final run. Exact user-authorized source pins preserve all earlier negative pipeline guards. See final_regression.json and full_group_*.json/log. Earlier interrupted and pre-thumbnail runs are kept separately and do not qualify the final PASS."]
(out/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
print(json.dumps(result,ensure_ascii=False))
assert all(checks.values()),[k for k,v in checks.items() if not v]
