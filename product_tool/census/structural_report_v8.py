"""Review exact structural contracts using saved fixtures, then render adapter matrix."""
from collections import Counter,defaultdict
import hashlib
import json
import re
from .structural_inventory_v8 import ROOT,OUTPUT,read,write,inventory
from .structural_contracts_v8 import LAYERS,cluster_profiles
from .structural_schema_v8 import validate_schema

PRIORITY=['jbl','samsung','lg','apple','playstation','microsoft','xbox','razer','hyperx','hiper','xiaomi_global','dreame','electrolux','bosch_home']

def contract_review(profiles):
    for p in profiles:
        for layer,e in p['layers'].items():
            e['contract_reviewed']=False
            if not e['observed'] or not e.get('fixture'):continue
            fixture=read(OUTPUT/e['fixture'])
            if fixture['signatures'][layer]!=e['signature'] or fixture['contracts'][layer]!=e['contract']:raise ValueError('fixture_contract_mismatch')
            identity=fixture['contracts']['identity']
            strong=identity['model_semantics']=='explicit_manufacturer_or_model' and bool(identity['variant_fields']) and fixture['is_product_page'] and fixture['product_objects']<=2
            if layer=='identity':enough=strong and bool(set(identity['code_fields'])&{'mpn','model'})
            elif layer=='specifications':enough=strong and any('additionalProperty[].' in path for path in e['contract']['json_paths'])
            elif layer=='media':enough=strong and any('.image.contentUrl' in path or '.image[].contentUrl' in path for path in e['contract']['json_paths'])
            elif layer=='discovery':enough=strong and bool(e['contract']['routes']) and bool(e['contract']['pagination'])
            else:enough=False  # Model-document-language association not proven by an href.
            e['contract_reviewed']=enough
            if enough:e['limitation']='Fixture confirms explicit manufacturer/model fields and variant context; reuse remains research-only.'
    return cluster_profiles(profiles)


def render():
    data=read(OUTPUT/'adapter_profiles.v1.json');profiles=data['profiles'];records,labels,families,missing,totals=inventory();by_id={r['profile_id']:r for r in records}
    for p in profiles:
        current=by_id[p['profile_id']]
        p['unique_products']=current['unique_products']
        p['category_scope']=current['category_scope']
        if p['profile_id']=='braun_household_global_candidate':p['division']='household_appliances'
        if p['profile_id']=='braun_personal_care_candidate':p['division']='personal_care'
        if p['source_family']=='electrolux':p['division']='home_appliances'
        p['missing_layers']=[layer for layer,e in p['layers'].items() if not e['observed']]
        if p['missing_layers']:p['review_notes']=list(dict.fromkeys(p['review_notes']+['Unobserved layers: '+', '.join(p['missing_layers'])]))
        if p['source_family'] in {'bosch_home','bosch_tools'}:p['coverage_note']=current['coverage_note']
        if p['division']=='support_portal' and 'bosch-diy.com' in p['official_domain']:p['division']='consumer_DIY_tools'
        # A set of detected layers is still partial until document model/language linkage is known.
        if p['completeness_status']=='adapter_profile_complete' and p['layers']['documents']['contract']['model_linkage'].startswith('unverified'):
            p['completeness_status']='structure_partial';p['review_notes'].append('Document model/language association remains unverified; five detected layers do not imply a complete adapter contract.')
    clusters=contract_review(profiles)
    cluster_map={(member,layer):c for layer,items in clusters.items() for c in items for member in c['members']}
    for p in profiles:
        for layer,e in p['layers'].items():
            c=cluster_map.get((p['profile_id'],layer))
            if c:e['status']=c['status']
    validate_schema(data,read(OUTPUT/'adapter_profiles.v1.schema.json'))
    write(OUTPUT/'adapter_profiles.v1.json',data);write(OUTPUT/'adapter_clusters.json',clusters)
    for name in ['adapter_profiles.v1.json','adapter_profiles.v1.schema.json']:
        (ROOT/'product_tool/config'/name).write_bytes((OUTPUT/name).read_bytes())
    grouped=defaultdict(list)
    for p in profiles:grouped[p['source_family']].append(p)
    rows=[]
    for family,ps in grouped.items():
        layer_ids={layer:sorted({cluster_map[(p['profile_id'],layer)]['cluster_id'] for p in ps if (p['profile_id'],layer) in cluster_map}) for layer in LAYERS}
        shared=[{'layer':layer,'cluster':c['cluster_id']} for layer,items in clusters.items() for c in items if family in c['source_families'] and c['status'] in {'shared_adapter_candidate','regional_shared_candidate'}]
        rows.append({'source_family':family,'profile_ids':[p['profile_id'] for p in ps],'official_domains':[p['official_domain'] for p in ps],'divisions':sorted({p['division'] for p in ps}),'access':dict(Counter(p['access_status'] for p in ps)),'protection':dict(Counter(p['protection_status'] for p in ps)),'CMS':sorted({c['engine'] for p in ps for c in p['cms_fingerprint']}),'layers':layer_ids,'javascript_dependency':sorted({p['javascript_dependency'] for p in ps}),'reuse_candidates':shared,'custom_work_required':sorted({layer for p in ps for layer,e in p['layers'].items() if e['status'] not in {'shared_adapter_candidate','regional_shared_candidate'}}),'manual_review':[{ 'profile_id':p['profile_id'],'reason':p['completeness_status'],'gaps':p['review_notes'],'next_action':p['next_action']} for p in ps if p['completeness_status']!='adapter_profile_complete'],'product_coverage':families.get(family,{}).get('unique_products',0),'profile_statuses':dict(Counter(p['completeness_status'] for p in ps)),'production_ready':False})
    unverified_labels={brand.casefold() for candidate in read(ROOT/'product_tool/config/source_candidates.v1.json')['candidates'] if candidate.get('official_status')!='official_verified' and candidate.get('source_role')!='retailer' for brand in candidate.get('brands',[])}
    mappings=[]
    for label in labels:
        family=label['source_family_id'];targets=grouped.get(family,[])
        if family=='bosch_category_routed':targets=grouped.get('bosch_home',[])+grouped.get('bosch_tools',[])
        if targets:status='verified_source_profiles_linked'
        elif label['final_status']=='official_source_not_found':status='official_source_missing'
        elif label.get('relationship') in {'unresolved','possible_typo'}:status='brand_identity_unresolved'
        elif label.get('review_status') in {'manual_research_required','human_review_required'}:status='manual_research_required'
        elif label['original_brand_label'].casefold() in unverified_labels:status='official_source_unverified'
        else:status='manual_research_required'
        mappings.append(dict(label,stage8_status=status,adapter_profile_ids=[p['profile_id'] for p in targets],next_action='Review structural profiles before adapter implementation.' if targets else 'Resolve brand identity.' if status=='brand_identity_unresolved' else 'Manual official-source research required; no adapter may be assigned.'))
    summary=read(OUTPUT/'run_summary.json')
    summary.update(registered_verified_family_labels=len(families),official_implementation_families=len(grouped)-('sulpak' in grouped),approved_dealer_families=int('sulpak' in grouped),routing_only_families=['bosch_category_routed'],profile_count=len(profiles),profile_status_counts=dict(Counter(p['completeness_status'] for p in profiles)),support_status_counts=dict(Counter(p['support_status'] for p in profiles)),catalog=totals,linked_product_coverage=sum(x['unique_products'] for x in mappings if x['adapter_profile_ids']),unresolved_label_counts=dict(Counter(x['stage8_status'] for x in mappings if not x['adapter_profile_ids'])),source_brand_labels=len(mappings),layer_cluster_counts={layer:dict(Counter(c['status'] for c in items)) for layer,items in clusters.items()},families_with_product_sample=sorted({p['source_family'] for p in profiles if p['sample_product_page']}))
    summary['complete_adapter_profiles']=sum(p['completeness_status']=='adapter_profile_complete' for p in profiles)
    summary['product_sample_family_coverage']=sum(families.get(family,{}).get('unique_products',0) for family in summary['families_with_product_sample'])
    summary['layer_product_coverage']={layer:sum(families.get(family,{}).get('unique_products',0) for family,ps in grouped.items() if any(p['layers'][layer]['observed'] and p['sample_product_page'] for p in ps)) for layer in LAYERS}
    summary['unresolved_label_counts'].setdefault('official_source_unverified',0)
    summary['structural_census_complete']=True
    test_log=(OUTPUT/'tests.txt').read_text(encoding='utf-8')
    summary['tests_run']=int(re.search(r'Ran (\d+) tests',test_log).group(1))
    summary['tests_passed']=test_log.rstrip().endswith('OK')
    priority_map=[next((r for r in rows if r['source_family']==family),{'source_family':family,'status':'official_source_unverified','product_coverage':0,'production_ready':False}) for family in PRIORITY]
    implementation=sorted(rows,key=lambda r:(r['source_family'] not in PRIORITY,not any(grouped[r['source_family']][i]['sample_product_page'] for i in range(len(grouped[r['source_family']]))),-r['product_coverage']))
    matrix={'schema_version':1,'production_ready':False,'summary':summary,'rows':rows,'brand_label_mapping':mappings,'priority_brand_map':priority_map,'recommended_sequence':[{'source_family':r['source_family'],'product_coverage':r['product_coverage'],'action':'Confirm missing product/variant/document contracts, then implement only approved layer profiles.','reuse_candidates':r['reuse_candidates']} for r in implementation if r['source_family']!='sulpak'],'dealer_policy':'Structural availability does not prove catalog product absence. Sulpak remains LG appliance allowlist only; all other dealer queues remain disabled.'}
    write(OUTPUT/'adapter_matrix.json',matrix);write(OUTPUT/'summary.json',summary)
    before=read(OUTPUT/'protected_hashes_before.json');after={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in before};changed=[p for p in before if before[p]!=after[p]]
    write(OUTPUT/'protected_hashes_after.json',{'before':before,'after':after,'changed':changed,'unchanged_count':len(before)-len(changed)})
    if changed:raise ValueError('Protected files changed: '+repr(changed))
    lines=['# Stage 8 — all-source structural adapter census','',f"Coverage: {len(profiles)} domain/division/support profiles across {summary['official_implementation_families']} official implementation families and the existing Sulpak dealer. Stage 3's 100 verified family labels include `bosch_category_routed`, a routing label rather than an additional website. It maps to separate Bosch Home and Bosch Tools profiles.",'',f"Complete adapter profiles: {summary['complete_adapter_profiles']}. Profile statuses: {summary['profile_status_counts']}. Support statuses: {summary['support_status_counts']}.",'',f"All {len(mappings)} original brand labels have explicit mappings or unresolved states. Linked product coverage: {summary['linked_product_coverage']} / {totals['unique_products']}. Unresolved: {summary['unresolved_label_counts']}.",'',f"New HTTP requests (including redirects): {summary['new_http_requests']}; unique existing snapshots reused: {summary['reused_snapshot_count']}; browser runs: 0. No production adapters, catalog exact-model searches, dealer activation or completed product cards were produced.",'',f"Coverage linked to verified source registries is not adapter readiness. Families with actual Product fixtures cover {summary['product_sample_family_coverage']} catalog products; layer evidence coverage: {summary['layer_product_coverage']}. Category-routed Bosch products are excluded from this evidence coverage until allocated.",'','## Layer compatibility','', 'CMS is recorded independently and never enters the cluster key. Signatures contain structure only, with identity semantics, variants, pagination and locale context. Shared status requires fixture-backed compatible contracts on independent implementations. Detected fields alone remain custom candidates when required-field/variant stability is unresolved.','']
    for layer,items in clusters.items():
        lines.append(f"- {layer}: {dict(Counter(c['status'] for c in items))}.")
        lines += [f"  - {c['cluster_id']}: {c['status']}; families {', '.join(c['source_families'])}; profiles {', '.join(c['members'])}." for c in items if c['status']!='custom_adapter_candidate']
    lines += ['', 'Detailed contracts, compatibility evidence and fixture references: [adapter_profiles.v1.json](adapter_profiles.v1.json), [adapter_clusters.json](adapter_clusters.json), [schema](adapter_profiles.v1.schema.json). Every record remains `production_ready=false`.', '', '## Source-family matrix','', '| Family | Coverage | Domains / divisions | Access / protection | CMS | Discovery | Identity | Specifications | Media | Documents | JS / review |','|---|---:|---|---|---|---|---|---|---|---|---|']
    for r in sorted(rows,key=lambda x:-x['product_coverage']):
        layer_cells=['<br>'.join(r['layers'][l]) or 'insufficient_evidence' for l in LAYERS]
        lines.append('| '+' | '.join([r['source_family'],str(r['product_coverage']),'<br>'.join(r['official_domains'])+'<br>'+', '.join(r['divisions']),str(r['access'])+' / '+str(r['protection']),', '.join(r['CMS']) or 'unknown',*layer_cells,', '.join(r['javascript_dependency'])+' / '+str(r['profile_statuses'])])+' |')
    lines += ['', '## Priority-brand adapter map', '', '| Family | Coverage | Observed status | Reuse | Next implementation work |','|---|---:|---|---|---|']
    for r in priority_map:
        lines.append('| '+' | '.join([r['source_family'],str(r['product_coverage']),str(r.get('profile_statuses',r.get('status'))),str(r.get('reuse_candidates',[])),', '.join(r.get('custom_work_required',[])) or 'Verify official source first'])+' |')
    lines += ['', 'HYPERX and HIPER are separate. Only the Microsoft support portal is verified in the preserved registry. An independent Xbox product portal is not verified in this scope and receives no adapter assignment. Bosch Home and Bosch Tools remain separate, with 84 category-routed products not arbitrarily allocated.', '', '## Gaps and recommendations','', '1. Shared adapters: only clusters explicitly marked shared/regional are justified; all others need custom contract work. CMS fingerprints and a bare JSON-LD Product type justify no shared adapter.', '2. Reuse candidates: low-level JSON-LD/microdata readers, specification-row parsing, srcset selection and safe document-link discovery are reusable primitives, not proof of a common brand adapter. Use the layer-specific fixture contracts before pooling implementations.', '3. Custom work: sources with observed Product contracts have concrete custom candidates; remaining sources need first-party product discovery or readable structured responses before implementation.', '4. HTTP limitations: blocked and JavaScript-only statuses are bounded observations at listed hosts/endpoints, not permanent brand-wide conclusions. Do not transfer browser protection to HTTP or regional mirrors.', '5. Dealer fallback: this census cannot establish exact-product absence. Keep every new dealer disabled. Only existing LG appliance Sulpak scope can be considered later after its ordinary identity/completeness gate; blocked Sulpak is not retried.', '6. Priority order: start with priority brands that have actual Product fixtures, ordered by product coverage, then close structural gaps for remaining priority brands. Implement no extraction until the matrix is approved.', '7. Documents/media: select only explicitly advertised original/high-resolution media URLs; do not invent CDN transforms. Require exact model association and explicit document language before document extraction. A support link or PDF alone is not sufficient.', '', 'Recommended sequence (coverage and observed product evidence): '+', '.join(r['source_family'] for r in implementation if r['source_family'] in PRIORITY)+'. This sequence is a recommendation only.', '', 'All unresolved labels and each profile gap include a reason and next action in [adapter_matrix.json](adapter_matrix.json). No unexplained research_pending rows remain. `product_page_not_found` means the bounded structural sample failed, not that catalog products are absent.', '', '## Sampling and preservation','', 'Homepage/category/product/support sampling uses saved HTTP snapshots first. New URLs originate in the verified registry or captured first-party links; product URLs are never invented or seeded from catalog models. Requests are limited to 5 per profile, 8 per exact host, 500 total, 700 KB responses and 35 seconds per profile, with low request frequency and redirect-chain host checks. Confirmed challenge/403/429 pauses the HTTP host without retries.', '', 'Only structural objects, sanitized provenance URLs, sample metadata and hashes are persisted. No raw new HTML, cookies, headers, tokens or product values are stored. Historical sanitized snapshots can omit media or embedded state; those omissions remain explicit gaps. Regional structures are not pooled without compatible fixture evidence.', '', f"All {len(before)} protected pre-existing files are byte-identical: Stage 2–7.1, registries, snapshots, catalog, browser policy, Sulpak allowlist, dealer exclusion, disabled dealers and user changes. [Hash audit](protected_hashes_after.json).", '', f"Tests: {summary['tests_run']}; passed: {summary['tests_passed']}."+' [tests.txt](tests.txt). Research files and declarations are separate from the production pipeline.']
    (OUTPUT/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=True))

if __name__=='__main__':render()
