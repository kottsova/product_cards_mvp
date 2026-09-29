"""Offline Stage 7 report artifacts; no network or browser imports."""
from pathlib import Path
from collections import Counter
import hashlib,json,sqlite3
from .runner_v5 import write_json
from .official_domains import load_domains
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'reports/source_census_2026-09-22_stage7'

def execute():
    data=json.loads((OUT/'final_results.json').read_text(encoding='utf-8'));initial=json.loads((OUT/'dry_run.json').read_text(encoding='utf-8'))
    before=json.loads((OUT/'protected_hashes_before.json').read_text(encoding='utf-8'));after={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in before};assert before==after
    write_json(OUT/'protected_hashes_after.json',after)
    raw=(OUT/'tests.txt').read_bytes();tests=raw.decode('utf-16') if raw.startswith(b'\xff\xfe') else raw.decode('utf-8-sig');(OUT/'tests.txt').write_text(tests,encoding='utf-8');assert 'Ran 233 tests' in tests and tests.rstrip().endswith('OK')
    observed={(r['source_family'],r['identity']['seller_sku']):r for r in initial['runs']}
    checked=[];queue=[];allowed=[];not_found=[];levels=Counter();unique_candidates=set();validations=0
    policy_evidence={
      'samsung':('sulpak_samsung_candidate','Sulpak','https://www.sulpak.kz/','KZ','https://www.samsung.com/kz_ru/buyoriginal/','manufacturer_lists_authorized_partner','Samsung explicitly lists Sulpak; this is not user approval.'),
      'karcher':('karcher_official_shop_candidate','Karcher official shop','https://karchershop.kz/','KZ','https://www.kaercher.com/kz/servis/podderzhka/tochki-prodazh.html','manufacturer_links_official_shop','Official store link confirmed; legal ownership/source role and coverage need review.'),
      'dreame':('dreame_amazon_store_candidate','Dreame Amazon storefront',None,'US','https://www.dreametech.com/pages/where-to-buy','manufacturer_lists_storefront','Only the manufacturer-linked storefront is a candidate, not arbitrary marketplace sellers; exact storefront URL and seller identity need review.'),
      'bosch_home':('bosch_kz_dealer_identification','Bosch branded-store dealer to identify',None,'KZ','https://www.bosch-home.com/kz/roznichniye-magaziny','locator_only_specific_dealer_unverified','Official branded stores are listed; no specific third-party web dealer ownership has been verified.')}
    for r in data['runs']:
        key=(r['source_family'],r['identity']['seller_sku']);old=observed.get(key,r);old_domains={d['domain_id']:d for d in old['domains']}
        if r['outcome']=='official_exact_product_not_found':not_found.append({'source_family':key[0],'seller_sku':key[1],'domains':r['domains_planned'],'scope':r['search_scope']})
        if r['dealer_fallback']['allowed']:allowed.append({'source_family':key[0],'seller_sku':key[1],'category':r['identity']['category_raw'],'gate':r['dealer_fallback'],'discovery':r.get('dealer_discovery')})
        for d in r['domains']:
            prior=old_domains[d['domain_id']]
            checked.append({'source_family':key[0],'seller_sku':key[1],'category':r['identity']['category_raw'],'domain_id':d['domain_id'],'market':d['market'],'url':d['url'],'outcome':d['outcome'],'http_requests':prior['http_requests'],'methods':sorted({p['discovery_method'] for p in d['requests']}),'access_statuses':sorted({p['access_status'] for p in d['requests']}),'protection_statuses':sorted({p['protection_status'] for p in d['requests']}),'candidates':d['candidates'],'requests':d['requests'],'selected_best':r['best_official']['domain_id']==d['domain_id'] if r['best_official'] else False,'truncated':d['truncated']})
            validations+=d['product_validations']
            for c in d['candidates']:
                unique_candidates.add(c['url']);levels[c['identity_verification'].get('level','not_validated')]+=1
        if key[0] in policy_evidence:
            id,name,url,market,evidence,status,note=policy_evidence[key[0]]
            queue.append({'candidate_id':id+':'+key[1],'source_family':key[0],'brand':r['identity']['brand_raw'],'category':r['identity']['category_raw'],'market':market,'name':name,'candidate_url':url,'enabled':False,'approval_status':'review_pending','fallback_reason':r['outcome'],'gate_currently_satisfied':r['outcome']=='official_exact_product_not_found','authorization_evidence':[{'url':evidence,'status':status,'note':note,'checked_at':'2026-09-22','access_method':'web_research'}],'proposed_coverage':'same category; exact SKU and variant coverage unmeasured','access_status':'not_checked','fields_may_supplement':['missing_dimensions','missing_weight','missing_material_or_configuration'],'field_coverage_status':'proposed_not_extracted','legal_source_role_status':'review_pending','may_participate_in_card':False})
    write_json(OUT/'domain_checks.json',checked);write_json(OUT/'official_exact_product_not_found.json',not_found);write_json(OUT/'allowed_dealer_fallbacks.json',allowed);write_json(OUT/'dealer_review_queue.json',queue)
    evidence=json.loads((OUT/'supplemental_access.json').read_text(encoding='utf-8'))
    registry=[]
    for domain in load_domains():
        row=domain.to_dict();observations=[x for x in evidence['observations'] if x['source_domain']==domain.domain_id]
        row['endpoint_access_observations']=observations;row['last_checked_at']=max((x['checked_at'] for x in observations),default='')
        row['discovery_results']=[{'seller_sku':d['seller_sku'],'outcome':d['outcome'],'truncated':d['truncated']} for d in checked if d['domain_id']==domain.domain_id]
        # Do not flatten one endpoint challenge into a universal domain status.
        row['access_status']='see_endpoint_access_observations' if observations else 'not_checked';row['protection_status']='see_endpoint_access_observations' if observations else 'not_checked'
        registry.append(row)
    write_json(OUT/'official_domain_registry.json',{'schema_version':1,'domains':registry,'production_mutated':False})
    matrix=['# Domain checks by catalog product','','| Family | SKU | Domain / market | Discovery methods | New HTTP | Candidates | Outcome |','|---|---|---|---|---:|---:|---|']
    for d in checked:matrix.append(f"| {d['source_family']} | {d['seller_sku']} | {d['domain_id']} / {d['market']} | {', '.join(d['methods'])} | {d['http_requests']} | {len(d['candidates'])} | {d['outcome']} |")
    (OUT/'domain_checks.md').write_text('\n'.join(matrix)+'\n',encoding='utf-8')
    connection=sqlite3.connect((OUT/'source_snapshots.sqlite3').resolve().as_uri()+'?mode=ro',uri=True);snapshot_rows=connection.execute('select id,source_url,content,content_sha256 from source_snapshots').fetchall();connection.close()
    for _,_,content,digest in snapshot_rows:assert hashlib.sha256(content.encode()).hexdigest()==digest
    snapshot_summary=[{'id':id,'url':url,'bytes':len(content.encode()),'sha256':sha} for id,url,content,sha in snapshot_rows];write_json(OUT/'snapshot_hashes.json',snapshot_summary)
    outcomes=Counter(r['outcome'] for r in data['runs']);total=data['initial_http_requests']+data['supplemental_http_requests']
    report=f'''# Stage 7: multi-domain official-source fallback - 2026-09-22

Stage 7 is implemented as a bounded research coordinator using ordinary HTTP and snapshots. Browser-assisted discovery is permanently excluded from automatic orchestration. Chromium is a separate manual diagnostic tool only after a new explicit user request. No browser run or browser-strategy change was made in Stage 7.

## Pilot result

Eleven real catalog products: LG 2, Bosch Home 2, Samsung 3, Karcher 2, Dreame 2. Total new HTTP requests: **{total}** (105 initial + 2 supplementary). Chromium launches: **0**. The initial pilot asserts that no browser, Playwright or Selenium module was loaded. Regression browser tests use fakes; the real Chromium fixture was not run.

Exact official identities: **0**. Outcomes: {dict(outcomes)}. There are {len(unique_candidates)} distinct candidate URLs across {len(checked)} product/domain checks; structured target validations, including reuse of already captured pages for another expected identity: {validations}. Per-candidate identity states: {dict(levels)}. Candidate text/URLs do not establish identity. Any displayed best candidate with insufficient identity is only the best review candidate, not an approved source for a card.

| Family | Catalog SKU | Final official outcome | Permitted dealer |
|---|---|---|---|
'''
    for r in data['runs']:report+=f"| {r['source_family']} | {r['identity']['seller_sku']} | `{r['outcome']}` | {r['dealer_fallback'].get('source_id') or 'none'} |\n"
    report+='''
Products were selected from the catalog's highest-coverage eligible categories using a deterministic sample rule, not from manually found product pages. LG samples cover washing machines/vacuums; Bosch dishwashers/ovens; Samsung TVs/vacuums/washing machines; Karcher vacuums/window cleaners; Dreame vacuums/robot vacuums. Whether a product is absent from a primary market is reported only as absence of validated exact evidence within the budget, not a global inventory claim.

The composite Samsung seller code `Jet_70_turbo/(VS15T7031R4/EV)` exposed a partial query (`Jet_70_turbo/`) in the existing model normalization. Final policy 7.0.1 conservatively returns `official_search_incomplete` for an incomplete canonical query. Existing identity/normalization code was not changed. A third Samsung sample, `WD10T654CBH/LD`, supplies a clean full-code check in another mass category. Initial observations remain in `dry_run.json`; final policy results are in `final_results.json`. The first ten decisions were rebuilt offline from their domain observations; their earlier checkpoints are incompatible under the final version. The additional Samsung sample reused prior HTTP snapshots and made only two new requests.

## Domain registry and routing

`product_tool/config/official_domains.v1.json` defines 17 official domain/market records: LG KZ/global/US/Korea, Bosch Home global/Germany/UK, Bosch Professional separately, Samsung KZ/US/Korea, Karcher KZ/global/Germany, Dreame global/US/Germany. Different market paths on a shared hostname are separate source records but not independent network hosts. All are disabled for production; explicit research opt-in is required for pilot records. The Bosch Tools branch is not selected for Home appliances.

Each record has family/brand, market/locale, global/regional scope, division/categories, ownership evidence, page/support/document allowlists, sitemap/search/catalog capabilities, priority, enabled/research status and status/timestamp fields. `official_domain_registry.json` adds the actual endpoint-scoped observations and per-product discovery results without mutating the configuration.

Primary ownership evidence: [LG country selector](https://www.lg.com/common/index), [Bosch international selector](https://www.bosch-home.com/), [Samsung location selector](https://www.samsung.com/sec/function/ipredirection/ipredirectionLocalList/), [Karcher corporate page](https://www.kaercher.com/int/inside-kaercher/company/about-kaercher.html), [Dreame regional/store links](https://www.dreametech.com/pages/where-to-buy). These are ownership/market evidence, not product identity. Web research was restricted to domain ownership and dealer authorization; product candidates came from reproducible HTTP page/sitemap/search parsing. Web-tool research calls are separate from the application's 107-request pilot accounting.

Domain iteration: primary, other verified markets/global domains, then category/division-specific records. Selection: exact_variant anywhere, exact_model anywhere, matched structured-evidence completeness, global only as a tie-breaker, then regional/priority. Unknown/conflicting identity never gains exactness from market preference. Tests demonstrate regional exact beating global family-only and regional richer evidence beating an equally exact global result.

## Access scope and protection

The Stage 6.1 LG challenge is retained only as a `browser` observation for `https://www.lg.com/kz/search?q=27ART10AKPL`. It does not pause HTTP. In this pilot LG KZ safely answered ordinary GET searches for F2J3HS0W and A9K-PRO1 and participated in sitemap discovery. No universal LG-domain block was inferred.

Every observation stores exact host, endpoint, access method, discovery method, HTTP/protection status and timestamp. A newly observed HTTP 403/429/challenge pauses that exact hostname for HTTP during this run. Other hostnames/access methods do not inherit it. Shared-host regional paths obey the same temporary HTTP host stop. Cached snapshots can be read without new traffic. The supplemental run restored the earlier host pauses instead of retrying protected hosts.

Dreame US produced an HTTP protection stop; other Dreame hosts continued. Sulpak also produced a protection stop during the first allowed LG fallback. The second eligible LG fallback consumed cached evidence and made zero new requests to Sulpak. No bypass, proxies, stealth, browser fallback or manually injected product URLs were used.

## Budget and completeness

Per product: at most four eligible official records and 40 actual HTTP requests. Per record: at most ten requests including redirects, three sitemap documents, 800 sitemap URLs, two generated declared GET queries, three target validations and 40 seconds. Responses are bounded to 1 MB, requests to eight seconds and at least a one-second interval. Dealer research, only after the gate, has a separate six-request cap. Shared-response cache hits do not consume new network budget and are explicitly identified in receipts.

Only declared safe GET forms/configured endpoints, robots-declared or configured sitemaps, explicit catalog/support indexes, typed Product/ItemList public endpoints, and candidate links from those responses can be used. No arbitrary embedded application state is traversed. This pilot had no configured structured endpoints; those paths are a contract for already confirmed endpoints, not a claim that APIs were tested.

`official_exact_product_not_found` means every eligible confirmed record in the selected registry was considered within the recorded limits, with discovery evidence and no pending candidate validation. It is not exhaustive global absence. Skipped domains, unvalidated candidates or a partial canonical query produce `official_search_incomplete`; no accessible discovery evidence produces `official_search_unavailable`. The latter two outcomes do not permit dealers. Sitemaps/indexes can remain truncated under the declared bounded scope; details are retained per domain.

## Dealer policy and review queue

Only LG/Sulpak's existing exact appliance allowlist was executable: washing machines, dryers, refrigerators, vacuums and microwave ovens. LG split systems remain review_pending; TV, monitors, audio and computing are excluded. Excluded dealers remain excluded even where an external manufacturer page lists it. Existing source registry/allowlist files are byte-for-byte unchanged.

Two LG cases pass the gate only after four official records each. Both Sulpak research results are protection-limited; no dealer identity or card data was accepted. See `allowed_dealer_fallbacks.json`.

`dealer_review_queue.json` is entirely disabled with `approval_status=review_pending`. Samsung/Sulpak has [manufacturer authorization evidence](https://www.samsung.com/kz_ru/buyoriginal/); Karcher's shop is linked by the [manufacturer's sales page](https://www.kaercher.com/kz/servis/podderzhka/tochki-prodazh.html), with legal ownership/source role still requiring review; Dreame's manufacturer-linked Amazon storefront needs exact seller/storefront scoping. Bosch has only a branded-store locator lead; a particular third-party web dealer remains unverified. Missing evidence is explicitly marked, not fabricated. Entries for incomplete official searches are conditional review leads, not current fallback authorizations. Proposed field coverage is unmeasured and no new dealer was used for a card.

## Field provenance and production boundary

The future card merge contract requires source, URL, fetched date, identity level, extraction method and confidence. Different variant keys are rejected. Existing ResolutionPolicy preserves confirmed manufacturer/support values; an approved dealer can fill an absent field, and a disagreement is logged for review while the official value is retained. No attributes/media/manual extraction or production card writes were performed.

The Stage 7 coordinator and registry are research components. Existing production routing/worker files and user modifications were not rewritten or deployed. This preserves the active registry while making the new policy concrete and testable; production adoption is a separate step.

## Artifacts and verification

- `domain_checks.md` / `.json`: every product/domain, method, new request count, candidates, identity, access/protection and rejection outcomes.
- `final_results.json`: final official result, best review candidate and dealer gate per product.
- `official_exact_product_not_found.json`: only cases passing the complete bounded official-search gate.
- `official_domain_registry.json`: research records plus scoped observed statuses.
- `http_cache.json`, `supplemental_cache.json`, `source_snapshots.sqlite3`, `snapshot_hashes.json`: captured responses and hash-verified immutable SourceSnapshot contents. Protection/error responses are metadata only; successful responses have sanitized content snapshots.
- `checkpoint.json`, initial/final result artifacts: no-network compatible resume and explicit version invalidation. Final policy replay used captured domain results; it is not represented as a new render or new HTTP check.
- `dealer_review_queue.json`, `allowed_dealer_fallbacks.json`: proposed disabled sources versus existing approved scope.

'''
    report+=f"Full regression: **233 tests passed** (`tests.txt`). All **{len(before)} protected files** retain their SHA-256 values, including Stage 2-6.1 reports/snapshots, existing registries, catalog, browser strategy, and pre-existing user changes. Therefore the 186 unresolved labels, Accesstyle negative result, Sulpak restrictions, dealer exclusion and HyperX evidence are preserved. {len(snapshot_rows)} new successful-response snapshots were hash-verified. The complete before/after manifests are included.\n\n"
    report+='''## Next stage recommendation

Next: offline canonical model-code/variant reconciliation for composite seller SKUs, plus human review of the disabled dealer queue and already recorded catalog coverage gaps. Use the captured candidates/snapshots to prioritize declared HTTP catalog endpoints; establish exact identity before field extraction or production adoption. Do not resume browser hardening and do not enable any new dealer automatically. This next stage was not implemented.
'''
    (OUT/'report.md').write_text(report,encoding='utf-8')
    write_json(OUT/'verification.json',{'tests':233,'protected_files':len(before),'protected_hashes_equal':before==after,'snapshots_verified':len(snapshot_rows),'chromium_launches':0,'total_http_requests':total,'outcomes':dict(outcomes),'unique_candidates':len(unique_candidates),'candidate_identity_states':dict(levels),'new_dealers_enabled':0})
    print(json.dumps({'protected':len(before),'snapshots':len(snapshot_rows),'outcomes':dict(outcomes),'candidate_states':dict(levels),'unique_candidates':len(unique_candidates)}))

if __name__=='__main__':execute()
