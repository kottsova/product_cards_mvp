"""Human-readable Stage 81 metrics backed by native output and original observations."""
import json,hashlib
from pathlib import Path
from collections import Counter,defaultdict
R=Path(__file__).parent;Q=R/'qualified_live_audit'
audit=json.loads((Q/'loss_report.json').read_text(encoding='utf8'));rows=audit['rows']
colors=json.loads((Q/'color_resolution.json').read_text(encoding='utf8'));gallery=json.loads((Q/'gallery_report.json').read_text(encoding='utf8'))
inventory=json.loads((Q/'category_inventory.json').read_text(encoding='utf8'));native=json.loads((Q/'native_ui_excel_qa.json').read_text(encoding='utf8'))
assert len(rows)==103 and len(inventory)==38 and all(r['live_official_data'] for r in rows)
assert all(r['useful_projection_loss']==0 and not r['duplicate_output_keys'] for r in rows)
assert native['attribute_rows']==sum(r['ui_rows'] for r in rows)
assert native['confirmed_photo_rows']==sum(r['confirmed_photos'] for r in rows)
assert sum(r['confirmed_photos'] for r in rows)==sum(r['byte_verified_photos'] for r in rows)
groups=defaultdict(Counter)
for r in rows:
 c=groups[r['brand']];c['models']+=1;c['raw_unique']+=r['unique_raw_rows'];c['canonical']+=r['canonical_rows'];c['photos']+=r['confirmed_photos'];c['verified']+=r['byte_verified_photos'];c['selected']+=r['selected_photos'];c['ready']+=r['readiness']['verdict']=='export_ready'
header=['# Stage 81 — cross-brand exhaustive attributes + photos audit','',
 'Frozen dataset: **103 inputs / 11 brands / 38 supported categories**. Selection was frozen before any run; no inputs were replaced.',
 '`SHA256: '+(R/'dataset.sha256').read_text().strip()+'`','',
 'Actual live: **103/103 official-data observations**, followed by **17 fresh affected reruns**. The qualified DB consolidates original live observations; consolidation and parser/UI QA are not additional live successes. Baseline, final live, delta live and image continuation evidence are kept separately. Same-run publisher/catalog cache is not historical capture replay.','',
 'No manual search stages were requested. `stages = [1,2,3,4]`; downloaded document inventory rows = 0. Apple procurement SKU PDF and PlayStation CFI documents were used only where model/hardware identity required them. Existing document evidence is retained under its original identity.','',
 f"Canonical output: **{sum(r['canonical_rows'] for r in rows)} rows**; native UI and Excel long attribute sheet: **{native['attribute_rows']} rows**. LG dimension aliases merge by the same scoped axis through the existing resolver; all source parents and real conflicts remain visible. Accepted source facts with unexplained projection loss: **0**. This does not assert that every raw paragraph has a safe canonical mapping.",'',
 f"Official gallery: **{sum(r['confirmed_photos'] for r in rows)} unique valid confirmed assets / {sum(r['byte_verified_photos'] for r in rows)} byte-verified**. Selected subset: **{sum(r['selected_photos'] for r in rows)}**. All confirmed assets appear in UI and `Фотографии`; unconfirmed assets remain candidates. Broken/blank/tiny/non-image media and unresolved URL templates are recorded as excluded, not silently dropped.",'',
 f"Official color confirmed for **{sum(r['confirmed'] for r in colors)}/103** inputs. Other colors remain explicitly unconfirmed; input configuration is not official evidence.",'',
 '| Brand | Inputs | Unique raw rows | Canonical | Confirmed gallery | Byte verified | Selected | Ready |','|---|---:|---:|---:|---:|---:|---:|---:|']
for brand,c in groups.items():header.append('| '+brand+' | '+' | '.join(str(c[k]) for k in ('models','raw_unique','canonical','photos','verified','selected','ready'))+' |')
header+=['','## Artifacts','',
 '- `dataset.json`, `category_coverage_frozen.json`: frozen selection and category coverage.',
 '- `qualified_live/observation_manifest.json`: original actual observation/job and phase per ID.',
 '- `qualified_live_audit/loss_report.json`: every raw classification, candidate/rejection reason and stored fact → output lineage.',
 '- `qualified_live_audit/category_inventory.json`: observed category → group → attribute union, roles, canonical keys, brands and model IDs.',
 '- `qualified_live_audit/gallery_report.json`: every saved/alias/excluded gallery row, role, relation, URL, dimensions, MIME, SHA and completion state.',
 '- `qualified_live_audit/color_resolution.json`: input color, official result, exact proof and ambiguity.',
 '- `CrossBrand_Stage81.xlsx`: native application export; local XLSX is intentionally Git-ignored.',
 '- `qualified_live_audit/native_ui_excel_qa.json`, `qa/final_ui/interaction_checks.json`: native output and browser interaction checks.','',
 '## Fixed common failures','',
 '1. Selected-only photo export and small gallery subsets; all valid owned assets now remain independently available.',
 '2. Rendition dedupe depended on equal SHA: resized bytes differ. Both published asset identity and equal bytes are now independent duplicate proofs; confidence/color/layout scopes remain isolated.',
 '3. Full photo metadata was tied to volatile SQL IDs. Stable source/asset/URL proof survives refresh.',
 '4. GIF was decoded as text despite format support; animated blank first frames were treated as placeholders. Binary preservation and sampled animation content are tested.',
 '5. Video and `{width}` / `*img*` templates entered image inventory. They are excluded with explicit reasons, without guessed URLs.',
 '6. Component/package dimension keys collided or lost published axis order; component scopes and explicit unit/order are preserved.',
 '7. Negative feature flags disappeared with empty-looking values, while missing physical quantities became false. Features survive; absent quantities remain unknown.',
 '8. Xiaomi mixed memory, conditional dimensions and eSIM sections dropped model-stable fields. Shared technologies/axes/connectivity recover independently of candidate capacities/colors/regions.',
 '9. Apple minimum/maximum brightness became a conflict; distinct modes now remain separate. Optional nano texture/TB5/configuration claims stay candidates.',
 '10. Branded Dreame and Electrolux capabilities were treated as prose; exact-owned capability presence is retained without admitting promotional percentages.',
 '11. Manuals ran during attributes/photos-only Apple refresh and prior document proof could be overwritten. No-search gates and identity-scoped historical proof retention are covered.',
 '12. English generic labels and missing parent groups; common vocabulary now supplies Russian labels and scoped groups while branded names remain intact.',
 '13. Long SHA metadata expanded CSS grid tracks, causing overlapping images/click interception. Bounded tracks, wrapping and normal clicks are verified on all 11 brands.','',
 '## Completeness limits','',
 'Attribute inventory is complete for the observed frozen output, not a claim that the entire category universe or every free-text source paragraph is canonically understood. Raw unsupported/conditional lines remain in the loss report with reasons; source conflicts are not suppressed.',
 'Photo completeness covers published assets admitted by existing model/configuration policy. Unproved color/layout/bundle/hardware relations stay candidates. PlayStation hardware inputs without a matching appearance source and the synthetic Electrolux revision are not forced ready.',
 'A 8540-second wall interval occurred in LG gallery completion while the ordinary worker job itself completed in six seconds. The overlapping offline regression also accumulated a long wall interval. Missing in-flight trace prevents attributing that interval to a particular HTTP/browser cause. Later gallery starts/ends/errors are durable in `gallery_timing.jsonl`; no speculative root cause is selected.','']
(R/'README.md').write_text('\n'.join(header),encoding='utf8')
table=['# Frozen actual-live results','', '| ID | Brand | Category | Model | Official color | Raw unique | Canonical | Candidate raw | All valid saved photos | Confirmed / byte-verified | Selected | Readiness |','|---:|---|---|---|---|---:|---:|---:|---:|---:|---:|---|']
escape=lambda v:str(v).replace('|',' / ').replace('\n',' ')
for r in rows:table.append('| '+' | '.join(map(escape,[r['id'],r['brand'],r['category'],r['model'],r['color'],r['unique_raw_rows'],r['canonical_rows'],r['candidate_raw'],r['all_photos'],str(r['confirmed_photos'])+' / '+str(r['byte_verified_photos']),r['selected_photos'],r['readiness']['verdict']]))+' |')
(R/'live_results.md').write_text('\n'.join(table)+'\n',encoding='utf8')
gaps=[{'id':r['id'],'brand':r['brand'],'model':r['model'],'readiness':r['readiness']['verdict'],'blocking':r['readiness']['blocking_gaps']} for r in rows if r['readiness']['verdict']!='export_ready']
(R/'remaining_gaps.json').write_text(json.dumps({'card_evidence_gaps':gaps,'raw_rejection_classes':dict(Counter(r['classification'] for d in audit['details'].values() for r in d['raw_rows']))},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print({'inputs':103,'categories':38,'canonical':sum(r['canonical_rows'] for r in rows),'native_attributes':native['attribute_rows'],'gallery':native['confirmed_photo_rows'],'ready':sum(r['readiness']['verdict']=='export_ready' for r in rows),'card_gaps':len(gaps)},flush=True)
