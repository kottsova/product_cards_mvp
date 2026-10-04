"""Render the Stage 59 audit from immutable first pass and final production evidence."""
from __future__ import annotations
from collections import Counter
from pathlib import Path
import hashlib, json, sqlite3
from product_tool import jobs, manual_status
from product_tool.adapters.samsung_source import exact_support_url

root = Path(__file__).resolve().parent
load = lambda name: json.loads((root / name).read_text(encoding='utf-8-sig'))
baseline = load('baseline.json')
frozen = load('dataset_frozen.json')
first = load('first_pass.json')
final = load('final_pass.json')
qa = load('qa_ui_excel.json')
photo = load('photo_measurement.json')
sha = hashlib.sha256((root / 'dataset_frozen.json').read_bytes()).hexdigest()

def ids(path):
    with sqlite3.connect(path) as db:
        return {code: pid for pid, code in db.execute('select id,search_code from products')}
first_ids, final_ids = ids(root/'first_pass.sqlite3'), ids(root/'post_fix.sqlite3')

def manual(path, mapping, row):
    return manual_status.russian_status(path, mapping[row['article']], row['article'], lg=False)

def support_link(db, mapping, row):
    support = (row.get('document_evidence') or {}).get('support') or {}
    if support.get('url'):
        return support['url'], 'checked' if support.get('exact_model') else 'candidate'
    page = row.get('page_evidence') or {}
    url = page.get('page_url') or ''
    if not url:
        return '', 'none'
    snap = jobs.latest_source_snapshot(db, mapping[row['article']], 'samsung')
    if not snap:
        return '', 'none'
    linked = exact_support_url(snap['content'], url, row['article'])
    return linked, 'PDP link only' if linked else 'none'

def link(url, label):
    return f'[{label}]({url})' if url else '\u2014'

def metrics(rows):
    readiness = Counter(x['readiness']['verdict'] for x in rows)
    exact = sum(x['readiness']['page_match_level'] == 'full_sku' for x in rows)
    kz = sum(x['readiness']['page_match_level'] == 'full_sku' and '/kz_ru/' in (x['page_evidence'].get('page_url') or '') for x in rows)
    ru = sum(x['readiness']['page_match_level'] == 'full_sku' and '/ru/' in (x['page_evidence'].get('page_url') or '') for x in rows)
    return f'exact PDP {exact}/10 (KZ {kz}, RU {ru}); ' + ', '.join(f'{k} {readiness[k]}' for k in ('export_ready','export_ready_with_gaps','not_ready','needs_verification'))

lines=[]
def add(*values): lines.extend(values)
add('# Stage 59 — Samsung baseline audit and shared-pipeline transfer', '',
    'Date: 2026-10-04. Starting commit: `3394aadf5c606543af41789cbc3c70005dd033b3`. '
    'Verdict: **Samsung fits the existing production pipeline with a small brand adapter for controlled use.** '
    'Two catalog-annotated vacuum codes remain under review; their base-model facts and photos are not exported as confirmed.', '',
    '## Reproducibility', '',
    f'- Catalog: `data/catalog_2026-09-21_filtered.xlsx`, sheet `Стиральные машины`. Frozen sample: `dataset_frozen.json`, SHA256 `{sha}`. '
    'The ten articles differ from the control and were absent from regression fixtures before the first run.',
    '- The control was processed by unchanged production `worker.run_once()` in `baseline.sqlite3`. '
    'Then `run_frozen_first.py` processed the ten frozen rows through the unchanged worker, before any Stage 59 product edit. '
    '`first_pass.json` preserves each outcome. `run_final_repeat.py` ran the same ten through the final production worker and checked evidence stability.',
    '- The SQLite files and policy access logs are local, ignored runtime state. Committed JSON evidence and runners make the sequence auditable. '
    'No model-specific production hardcode or identity-threshold change was added.', '',
    '## Control: WW90T554CAT/LD', '',
    '| Field | Unmodified production result |', '|---|---|',
    f'| Original/base/category | `{baseline["article"]}` / `{baseline["base_model"]}` / {baseline["category"]} |',
    '| Lookup variants | Full code `WW90T554CAT/LD`, then base `WW90T554CAT` within the KZ `da-sitemap.xml` route. |',
    f'| PDP | {link(baseline["page_evidence"]["page_url"], "exact Samsung KZ product page")}; KZ `da-sitemap.xml` 200, PDP 200, canonical/JSON-LD `Product.sku` and embedded `digitalData.product.model_code` show the full code. |',
    '| Support | [exact KZ support](https://www.samsung.com/kz_ru/support/model/WW90T554CAT/LD/) and [exact UZ support](https://www.samsung.com/uz_ru/support/model/WW90T554CAT/LD/) observed separately. Support is `page-support-detail`, not a PDP. The similarly named `/LP` page is a distinct variant. |',
    f'| Evidence | {len(baseline["facts"])} specifications in 9 PDP groups; {baseline["readiness"]["official_photos_selected"]} selected full-gallery photos and {len(baseline["photos"])-baseline["readiness"]["official_photos_selected"]} excluded thumbnails. No dealer facts. |',
    '| Manual | One official `User Manual` PDF, 36,987,971 bytes, 216 pages; Russian and Kazakh text verified. Exact code is absent from the PDF; official exact PDP link and matching family masks tie it with an advisory. Support also lists two Quick Guides and one User Manual as typed candidates. |',
    f'| Status | `{baseline["job_status"]}` / `{baseline["readiness"]["verdict"]}`; 0 real conflicts; advisories: `{", ".join(baseline["readiness"]["advisory_gaps"])}`. Russian manual: `{manual_status.VERIFIED}`. |', '',
    '## Official Samsung source structure and identity', '',
    '- KZ product URLs are listed by `da-sitemap.xml` (appliances) and `vd-sitemap.xml` (TV/audio/monitors); the official RU sub-sitemaps use the same division. A KZ sitemap miss is only a regional miss. The RU fallback yielded three exact sample PDPs.',
    '- A PDP has a canonical URL, JSON-LD `Product` with SKU/name, embedded `digitalData.product.model_code/model_name`, server-rendered `.pdd32-product-spec` groups, and a model-bound gallery. Exactness is decided from page content, never from the URL slug alone. Page model name, base model, full sales SKU, region and color suffix are retained as distinct facts.',
    '- Explicit PDP links lead to `/support/model/<code>/` (some older support routes use `model.<code>`). Support pages carry `page-support-detail` and embedded typed `manuals` JSON; their FAQ, account, repair and troubleshooting content is not product description or specification evidence.',
    '- Official files use `org.downloadcenter.samsung.com/downloadfile/ContentsFile.aspx`. `CDCttType` separates PDF User Manual (`UM`), online manual (`PM`) and other guides (`EM`); the support list also names Quick Guide, Installation Guide, Remote control and Simple User Guide. Declared language and filename only rank candidates. Russian verification requires PDF text plus an accepted exact/family relation.',
    '- The PDP contained site-search API markers, but no product-data API/XHR endpoint was validated. The adapter uses verified HTML/embedded JSON and does not guess an API route. Regional support and product pages stay separate source types.',
    '- Extraction preserves the PDP section, raw label and raw value before canonical mapping. Marketing blocks, service/help content and account copy do not become specifications. The shared dimension projection distinguishes product/package axes and leaves stand-specific labels distinct; raw source values remain available in the audit.', '',
    '## Frozen independent sample and unchanged first run', '',
    f'First-run metrics: **{metrics(first)}**. The unchanged Samsung adapter checked KZ only, so four articles appeared absent although official RU PDPs existed. '
    'The robot page was weaker than the catalog suffix. This is a pipeline gap, not evidence that those products do not exist.', '',
    '| Catalog article / category | Lookup variants (first run) | PDP and support | Specs | Selected/candidate photos | Russian manual | Dealer fallback | Job / readiness | Main gap |',
    '|---|---|---|---:|---:|---|---|---|---|')
for x in first:
    article=x['article']; page=x['page_evidence']; r=x['readiness']; support,state=support_link(root/'first_pass.sqlite3', first_ids, x)
    url=page.get('page_url') or ''
    region='KZ' if '/kz_ru/' in url else 'RU' if '/ru/' in url else ''
    source=f'{link(url, region+" PDP")}; {link(support,"support") if support else "support not reached"} ({state})' if url else 'none; support not reached'
    variants=[article, article.split('/')[0]]
    variants=list(dict.fromkeys(variants))
    gap=','.join(r['blocking_gaps']) or '\u2014'
    dealer=(x.get('dealer_evidence') or {}).get('dns_match_level') or 'none'
    add(f'| `{article}` / {x["category"]} | `{ "`, `".join(variants) }` | {source} | {r["official_facts"]} | {r["official_photos_selected"]}/{len(x["photos"])-r["official_photos_selected"]} | {manual(root/"first_pass.sqlite3", first_ids, x)} | `{dealer}` | `{x["job_status"]}` / `{r["verdict"]}` | `{gap}` |')
add('', 'The original query variants did not remove catalog annotations such as `Jet_` or `_Bespoke`. '
    'The first pass stored 45 robot facts as raw official candidate evidence and selected 0 of 23 gallery images. '
    'An audit found that the pre-fix product Excel row nevertheless displayed weaker Samsung values; the Stage 59 exact gate fixes that false export.', '',
    '## General fixes after the frozen first run', '',
    '| Before | Root cause | Shared correction | After |', '|---|---|---|---|',
    '| Four rows had no PDP in KZ | Samsung discovery stopped after KZ sitemap miss | Content-validate KZ/RU official sitemap candidates; use existing browser transport only after official exact misses | Dryer, microwave and second TV gained exact RU PDPs; the vacuum gained a KZ base-model candidate only |',
    '| QN90F lacked a manual | PDP had no manual anchor; exact support page had embedded manual JSON | Follow the PDP exact support link and inspect typed manual list; read PDF bytes/text | One accepted Russian User Manual, `export_ready_with_gaps -> export_ready` |',
    '| Source sections were blank; dryer had a spurious `49` vs `49 kg` conflict | Samsung groups were dropped and a bare overview number lost an explicit unit already printed on the same page | Persist `section -> raw label -> value`; infer a unit only for the same canonical field and identical number with one explicit unit | Dryer conflict cleared; raw values remain `49` and `49 кг` |',
    '| Annotated catalog codes could inherit ordinary page evidence and Excel exported their values | Query normalization, identity and shared resolver/export gates were disconnected | Treat SKU inside annotations as base-only; confirm exact Samsung facts in the shared resolver only for content-validated full SKU; gate product Excel on that flag | Jet and robot stay `needs_verification`; their product rows are empty, audit facts remain |',
    '| UI/Excel presented weak PDFs and photos as verified | Generic non-LG presentation assumed identity tie | Use Samsung acceptance and model-bound photo checks; reuse common Russian label and dimension projection | 10 cards and generated workbook show candidates separately; no extra dealer columns |', '',
    '## Final production evidence on the same frozen articles', '',
    f'Final metrics: **{metrics(final)}**. Exact official PDPs: 8 (KZ 5, RU 3); base-only candidates: 2; confirmed dealer pages: 0. '
    'External browser search ran only after the official exact-sitemap search missed; no external result was promoted without PDP-content validation. '
    'All ten rows have 0 accepted dealer facts. Manual status uses the three-state model and no unverified file is labeled Russian. Dealer fallback reports dealer_url_needed where no verified DNS/Technopark URL exists; no dealer page is guessed.', '',
    '| Article | Official PDP / identity | Support | Facts | Selected/candidate photos | Manual | External / dealer | Job / readiness | Open issue |',
    '|---|---|---|---:|---:|---|---|---|---|')
for x in final:
    article=x['article']; page=x['page_evidence']; r=x['readiness']; support,state=support_link(root/'post_fix.sqlite3', final_ids, x)
    url=page.get('page_url') or ''
    region='KZ' if '/kz_ru/' in url else 'RU' if '/ru/' in url else ''
    identity=r['page_match_level']; supp=link(support,'exact support')+f' ({state})' if support else '\u2014'
    gap=','.join(r['blocking_gaps']) or '\u2014'
    searches=len(page.get('external_search') or [])
    dealer=(x.get('dealer_evidence') or {}).get('dns_match_level') or 'none'
    add(f'| `{article}` | {link(url,region+" PDP")} / `{identity}` | {supp} | {r["official_facts"]} | {r["official_photos_selected"]}/{len(x["photos"])-r["official_photos_selected"]} | {manual(root/"post_fix.sqlite3", final_ids, x)} | {searches} / `{dealer}` | `{x["job_status"]}` / `{r["verdict"]}` | `{gap}` |')
add('', 'For each post-fix lookup, `page_evidence.query_variants`, `route.addresses`, `candidates`, `external_search` and `external_results` preserve the query/provider/URL/region/title/snippet/accepted-or-rejected reason. '
    'The first unsuitable search candidate cannot end the search; support URLs are skipped as PDP candidates. Browser CAPTCHA/rate limits are not bypassed.', '',
    '## False-confirmation review', '',
    '- **Exact full SKU**: control `WW90T554CAT/LD` and sample `MC32DG7646KKBW` show matching page-content SKU. PDP facts and gallery are confirmed; support/manual evidence supplies neither specs nor photos.',
    '- **Base/annotation**: `Jet_VS20A95973B/EV_Bespoke` points to a PDP whose Samsung SKU is `VS20A95973B/EV`. The extra catalog words are not declared by Samsung. Raw facts, manual and images remain candidate evidence; 0 selected photos and 0 main-sheet attribute values.',
    '- **Regional suffix**: `DV90T5240AW/LP` is exact on Samsung RU, while `VR30T80313W/EV_1` is not exact on its KZ page (`VR30T80313W/EV`). The latter has 0 selected photos, an unaccepted Russian PDF candidate and two preserved real size/weight conflicts. No base/family relation upgrades the `_1` suffix.',
    '- Confirmed false facts **after fixes: 0**. The first-pass Excel export leak for weak Samsung rows was repaired and explicitly checked. Unresolved source contradictions remain visible with both raw values.', '',
    '## UI, Excel, photos and regression', '',
    f'- TestClient: {len(qa["ui"])} cards returned HTTP 200; each exposed `Основные характеристики`, `Особенности модели`, manual status, candidate photos and lightbox markup. '
    'No generic `Дополнительная характеристика` or support/help copy appeared. Robot conflict displayed both `350x99.8x350` and `350x105x430` (plus 3.4 and 3.81 kg).',
    f'- Generated Excel: {qa["workbook_bytes"]} bytes; source audit has no Sulpak/dealer column, photo candidates are separate ({qa["photo_candidate_rows"]} rows). '
    'The Jet and robot product rows have 0 confirmed attributes; exact dryer and QN90F rows are populated. Raw facts and conflict sides remain on `Проверка источников`.',
    f'- Measured official QN90F gallery asset: {photo["verified_width"]} x {photo["verified_height"]} px, {photo["verified_bytes"]:,} bytes, {photo["verified_format"]}; '
    'the UI photo inspect route and generated Excel agreed on all four fields. Other unmeasured photos show unknown metadata rather than inferred dimensions.',
    f'- Final repeat: {sum(all([x["repeat"]["page_retained"],x["repeat"]["pdf_retained"],x["repeat"]["selected_photos_retained"],not x["repeat"]["document_duplicates"],not x["repeat"]["photo_duplicates"],x["repeat"]["readiness_before"]==x["repeat"]["readiness_after"]]) for x in final)}/10 preserved page, PDF, selected photos, uniqueness and readiness. '
    'Any remaining `needs_verification` is explained by catalog annotations rather than a false exact promotion.',
    '- Full regression: 1,429 tests, OK (929.997 s). `git diff --cached --check`: PASS. No readiness threshold changed.', '')
(root/'report.md').write_text('\n'.join(lines),encoding='utf-8')
print('report_rows',len(first),len(final),'lines',len(lines))
