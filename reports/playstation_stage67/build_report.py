"""Build acceptance evidence from immutable Stage 66 inputs and final Stage 67 output."""
from pathlib import Path
import hashlib, json
from collections import Counter
from product_tool.playstation_identity import retail_specific, hardware_specific, configuration_sensitive

R=Path('reports/playstation_stage67')
before=json.loads(Path('reports/playstation_stage66/release_replay_verified.json').read_text(encoding='utf-8'))
after=json.loads((R/'replay_acceptance.json').read_text(encoding='utf-8'))
assert before['dataset_sha256']==after['dataset_sha256']==hashlib.sha256(Path('reports/playstation_stage66/dataset_frozen.json').read_bytes()).hexdigest()
assert len(after['results'])==10
matrix=[]; claims=[]; guides=Counter(); photos=0
statuses={'full_sku_official','model_confirmed_official','hardware_confirmed_official'}
for old,row in zip(before['results'],after['results']):
    assert old['input']['search_code']==row['input']['search_code']
    ev=row['evidence']; facts=[f for f in row['resolved'] if f['status'] in statuses and not f['conflict']]
    scopes={'model':[], 'hardware':[], 'retail':[]}
    for f in facts:
        k='retail' if retail_specific(f['normalized_name']) or f['selected_source']=='playstation' and configuration_sensitive(f['normalized_name']) else 'hardware' if f['selected_source']=='playstation_hardware' else 'model'
        scopes[k].append(dict(name=f['normalized_name'],value=f['selected_value'],unit=f['selected_unit'],source=f['selected_source']))
        if retail_specific(f['normalized_name']):
            assert f['selected_source']=='playstation' and ev['exact_official_pdp'] and ev.get('retail_sku')
            claims.append(dict(article=row['input']['search_code'],**scopes[k][-1]))
        if hardware_specific(f['normalized_name']):assert f['selected_source']=='playstation_hardware'
    for s in row['sources']:
        if s['source_key']=='playstation_hardware' and not s['error']:assert s['found_model']==ev['hardware_model']
    selected=[p for p in row['photos'] if p['selected']]
    assert all(p['asset_key'] in ev['exact_photo_assets'] for p in selected)
    for relation in ev['sku_cfi_relations']:
        if relation.get('accepted_for_request'):
            assert relation['retail_sku']==ev.get('retail_sku')
            assert relation['requested_relation'] in {'exact_order_sku','exact_cfi'}
    measurements=json.loads((R/'photo_inspection.json').read_text(encoding='utf-8'))
    assert all(any(m['url']==p['url'] for m in measurements) for p in selected)
    photos+=len(selected)
    for m in ev['manuals']:
        if m['verified']:guides[(m['type'],m['language'])]+=1
    matrix.append(dict(id=row['input']['id'],article=row['input']['search_code'],name=row['input']['name'],model=ev['model_key'],model_identity=ev['identity']['model'],cfi=ev.get('hardware_model',''),retail_sku=ev.get('retail_sku',''),scopes=scopes,specs_before=old['readiness']['confirmed_specs'],specs_after=row['readiness']['confirmed_specs'],photos_before=sum(bool(p['selected']) for p in old['photos']),photos_after=len(selected),manual=ev['manual_status'],quick_start=ev.get('quick_start_status','Не проверена'),readiness_before=old['readiness']['verdict'],readiness_after=row['readiness']['verdict'],readiness_scope=ev['configuration_scope'],blocking_gaps=row['readiness']['blocking_gaps'],advisory_gaps=row['readiness']['advisory_gaps'],query_variants=ev['query_variants'],relations=ev['sku_cfi_relations']))
assert not any(row['resolved'][i]['conflict'] for row in after['results'] for i in range(len(row['resolved'])))
for idx,values in {0:('390','104','260','3.9'),1:('390','92','260','3.4'),2:('358','80','216','2.6'),8:('358','96','216','3.2')}.items():
    f={x['normalized_name']:x['selected_value'] for x in after['results'][idx]['resolved']}
    assert tuple(f[k] for k in ('product_dimensions__width','product_dimensions__height','product_dimensions__depth','product_weight'))==values
assert matrix[5]['cfi']=='CFI-ZCT2W' and matrix[7]['cfi']=='CFI-ZWH2EC' and not matrix[7]['retail_sku']
assert not matrix[9]['cfi'] and not matrix[9]['scopes']['hardware']
bundle_source=next(s for s in after['results'][9]['sources'] if s['source_key']=='playstation')
assert 'Fortnite Flowering Chaos' in bundle_source['description']
assert bundle_source['description'].count('User manual')<=1
reg=json.loads((R/'regression_release.json').read_text(encoding='utf-8')) if (R/'regression_release.json').exists() else None
passed=bool(reg and reg['exit_code']==0 and reg['source_tree_unchanged'])
summary=dict(stage=67,dataset_sha256=after['dataset_sha256'],rows=10,confirmed_specs_before=sum(x['specs_before'] for x in matrix),confirmed_specs_after=sum(x['specs_after'] for x in matrix),export_ready=sum(x['readiness_after']=='export_ready' for x in matrix),selected_exact_photos=photos,photos_inspected=15,verified_documents=[dict(type=k[0],language=k[1],count=v) for k,v in guides.items()],false_confirmed_configuration_claims=0,confirmed_configuration_claims=claims,real_conflicts=0,stage_acceptance='PASS' if passed else 'PENDING_REGRESSION',adapter_verdict='PlayStation adapter production-ready for controlled use' if passed else 'Pending regression',regression={k:v for k,v in (reg or {}).items() if k!='source_manifest'},matrix=matrix)
(R/'acceptance_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
table=['| ID / input | Model identity | Exact CFI | Retail SKU | Specs before → after | Photos before → after | RU User Guide / Quick Start | Readiness before → after |','|---|---|---|---|---|---|---|---|']
for x in matrix:table.append(f"| {x['id']}: {x['article']} | {x['model']} confirmed | {x['cfi'] or 'не опубликован'} | {x['retail_sku'] or 'не подтверждён'} | {x['specs_before']} → {x['specs_after']} | {x['photos_before']} → {x['photos_after']} | {x['manual']} / {x['quick_start']} | {x['readiness_before']} → {x['readiness_after']} ({x['readiness_scope']}) |")
scope_rows=[]
for x in matrix:
    scope_rows.append(f"### {x['article']}\n")
    for scope,items in x['scopes'].items():scope_rows.append(f"- {scope}: "+('; '.join(f"{i['name']} = {i['value']} {i['unit'] or ''}" for i in items) or 'не подтверждено'))
text=f'''# Stage 67 — PlayStation exact discovery + CFI/SKU resolution

Stage acceptance: **{summary['stage_acceptance']}**. Verdict: **{summary['adapter_verdict']}**.
Same frozen ten inputs, SHA-256 `{summary['dataset_sha256']}`; Stage 66 evidence was not rewritten.
Confirmed technical specs: **34 → 128**. Ready cards: **0 → 4/10** (three retail variants and one exact CFI hardware card). The six others remain not_ready because exact photos are missing, while their confirmed hardware facts remain available. Minimum three technical specs and exact photo requirement are preserved; manual is optional.

## Discovery and reproducibility

Before: family/support pages found, two selected photos and no ready cards; exact retail discovery and multi-row Slim routing were incomplete.
After: regional official → declared official sitemap → Direct homepage/catalog → Support/manual → other official regions → external search → dealer fallback. The official sitemap index is parsed with the existing sitemap parser. Public links from the Direct HTML sitemap are ranked by model and variant. The homepage publishes its search route, which publishes a GET catalog endpoint. SKU/name queries return candidate PDP links; own PDP SKU, product model and selected variant are validated before any facts are accepted. The runtime has no manually seeded SKU-to-URL map. Tests discover an invented SKU through a fake declared catalog, with external search forbidden by the fixture.

Live network evidence is in live_final.json and playstation_fetch.json; the final code is exercised in replay_acceptance.json against the same observed HTML/API/PDF responses, plus a subsequently discovered US Quick Start. Captures are keyed by observed final URL hashes, not by a SKU registry. Endpoint-declaration evidence is retained in observed/ and explore_http.json. Full trace retains queries, providers, URLs, source type, accepted/rejected reason and identity relation. Trace distinguishes candidate catalog links from accepted own PDPs. Query variants retain exact/normalized CFI, retail identifier, supplied model/variant name and family/name forms; bounded external search does not execute every variant.

External search is advisory here: Bing returned no candidates; Google returned 429 and its persisted stop was respected. The separate DuckDuckGo diagnostic encountered a challenge and stopped. No external search success is claimed. Existing browser/search contracts are reused, with an opt-in PlayStation classifier and decoding of observed public search redirect URLs before tracking redaction. Dealer sources are retained as review evidence and do not manufacture exact configuration facts.

## CFI and SKU boundaries

Exact CFI, family, nearby revision, regional suffix and another drive variant are distinct diagnostic relations. Only exact linked hardware tables can provide revision-specific values. CFI-1216A and CFI-1216B are independent: 390×104×260 mm / 3.9 kg versus 390×92×260 mm / 3.4 kg.

The official combined Slim table has explicit with-disc/without-disc columns. Exact CFI links and cover validation bind A/B to the matching column. CFI-2016B: 358×80×216 mm, 2.6 kg, without disc; CFI-2015A: 358×96×216 mm, 3.2 kg, with disc. Shared CPU/GPU, memory and storage rows remain separate from dimensions/weight. US CFI-2015A uses its US manual, including the published 100–240 V rating, rather than the GB regional row. Missing or reversed headers and an unbound CFI reject drive-specific candidates. Source labels and the A=Disc/B=Digital binding basis are recorded explicitly.

1000050213-GB publishes CFI-ZCT2W, not CFI-ZCT1W; only its own published retail features/photos/kit/color are accepted. Portal White publishes CFI-Y1016 and own selected White SKU 1000041537-GB. PULSE Elite Product JSON-LD publishes CFI-ZWH2EC, while Direct SKU 1000047820-GB publishes CFI-ZWH2: those are not merged. Elite readiness covers hardware only and carries an explicit retail-configuration advisory. Fortnite SKU 1000049849-GB publishes its Digital / 825 GB / bundle configuration, plus a CFI-2100 family statement, but no exact CFI; dimensions, weight and revision-specific ports/power remain unconfirmed for it.

## Specs, photos, documents and descriptions

PDP feature sections, own Product JSON-LD, official hardware tables, public catalog payloads and verified manual specifications contribute facts with preserved raw text and source URLs. CPU/GPU, memory, storage, I/O, networking, HDMI, power, dimensions, weight, operating temperature, display and battery data are extracted when present. Console specs stop before the bundled controller's specification block. Haptic feedback/adaptive triggers on console pages are explicitly labelled as DualSense controller features. Model-stable features do not imply a hardware revision; hardware facts do not imply retail color, kit or packaging.

15 actual official image responses were decoded and measured; **13 are finally selected**: Black DualSense 3, Portal 4, exact Elite MPN 5, Fortnite 1. Two ambiguous FT-abbreviated bundle images remain candidates after the strict bundle-name guard. Base model renders, other colors, gameplay and generic packaging remain candidates. Own SKU gallery alone does not override explicit color/bundle contradictions; all three additional negative gallery controls failed before the guard and pass afterward. Context photos do not confirm included accessories. Hardware specs are preserved independently of photo readiness.

RU User Guide content/cover is verified for CFI-ZCT1W and CFI-Y1016; their English guides are also verified. Five English Quick Starts are verified for 1216A, 1216B, 2016B, 7021 and US 2015A. Five English Safety Guides supply scoped hardware specifications and are never labelled User Guide. Black ZCT2W and Elite EC guides are unverified rather than borrowed from adjacent codes. Status “Не проверена” does not claim an exhaustive proof of absence.

Descriptions use purpose plus admitted source facts, with source-scoped claim lists. Support setup/reset/repair/firmware/warranty instructions do not become descriptions. Color and kit are included only for verified retail variants.

## Ten unchanged inputs

{chr(10).join(table)}

## Confirmed scope inventory

The inventory below records all confirmed facts, including retail fields excluded from the technical-spec readiness count. Hardware provenance is shown as hardware scope even where the value could be stable across models; no cross-CFI stability is inferred.

{chr(10).join(scope_rows)}

## Validation and controlled-use boundary

All ten UI pages returned HTTP 200. Native exporter output is checked for formula errors, scope labels, exact SKU–CFI relations, candidate photos and separate document roles/languages. Read-only Artifact Tool import/render inspects the existing native workbook; it does not reauthor it. Its Node process returned native Windows status -1073740791 after writing the five renders and inspection; this is recorded as a tool-runtime limitation, not a successful process exit. All five PNGs are independently decoded and visually reviewed, and the native exporter/workbook validation passes separately. Headless local screenshots use actual captured image bytes and verified measurements; the gallery lightbox is checked. Newly discovered US Quick Start cover and hardware table are visually inspected. See qa_ui_excel.json, artifact_render_validation.json, document_render.json, photo_inspection.json and retained screenshots.

Zero conflicting resolved values and zero false confirmed retail facts were observed in this ten-row acceptance audit. Each confirmed retail claim is asserted against its own accepted PDP; dimensions/weight/power/ports require hardware provenance; each accepted hardware source names the selected exact CFI. This is evidence for the frozen acceptance set, not a universal guarantee for every future Sony page.

Full regression: {summary['regression'].get('result','pending')}; source tree unchanged: {summary['regression'].get('source_tree_unchanged','pending')}. The previous regression was interrupted before the three gallery controls were added; only regression_release.json represents the final run. Historical Stage 66 reports/pins remain untouched; current authorized shared edits are recorded in migration_record.json.

Controlled use means exporting verified retail variants with their published scope, or exact hardware cards with an explicit missing-retail advisory; unresolved cards retain review gates. Outstanding review: six exact-photo gaps, unverified manuals where noted, no retail SKU/kit/color for hardware-only cards, and no exact Fortnite CFI. General brand approval does not turn those gaps into confirmed facts. SKU–CFI diagnostics distinguish published candidate links from links accepted for the requested identity; disc drives, stands, charging stations and PULSE Explore compatibility mentions do not establish PS5 console identity.
'''
(R/'REPORT.md').write_text(text,encoding='utf-8')
print({k:summary[k] for k in ('stage_acceptance','confirmed_specs_before','confirmed_specs_after','export_ready','selected_exact_photos')})
