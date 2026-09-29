"""Complete verified-source inventory and HTTP-only historical evidence index."""
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
import json
import sqlite3
from contextlib import closing
from .structural_contracts_v8 import inspect_structure
from .search_routes import safe_url

ROOT=Path(__file__).resolve().parents[2]
OUTPUT=ROOT/'reports/source_census_2026-09-22_stage8'

def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def write(path,value):Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def inventory():
    census=read(ROOT/'reports/source_census_2026-09-22_stage3/census.json')
    labels=census['labels'];families={x['source_family_id']:x for x in census['families'] if x['verified']}
    by_label={x['original_brand_label'].casefold():x['source_family_id'] for x in labels}
    records=[]
    for file,key in [('source_catalog.v2.json','sources'),('source_candidates.v1.json','candidates'),('source_research.v1.json','families')]:
        for raw in read(ROOT/'product_tool/config'/file)[key]:
            if raw.get('official_status')!='official_verified' and raw.get('source_id')!='sulpak':continue
            aliases=raw.get('brands',raw.get('source_labels',[]))
            sid=raw.get('source_id',raw.get('candidate_id',raw.get('source_family_id')))
            family=raw.get('source_family_id') or ('bosch_tools' if sid=='bosch_tools' else 'bosch_home' if sid=='bosch_home' else by_label.get(aliases[0].casefold()) if aliases else sid)
            if sid=='sulpak':family='sulpak'
            records.append({'profile_id':sid,'source_family':family,'brand_aliases':aliases,'division':sid if 'bosch' in sid or 'electrolux' in sid else raw.get('source_role','manufacturer'),'category_scope':raw.get('category_groups') or raw.get('category_allowlist',[]),'market':raw.get('market',','.join(raw.get('markets',[]))) or 'global','locale':raw.get('source_locale','unknown'),'official_domain':raw['candidate_url'],'allowed_hosts':sorted(set(raw.get('page_hosts',[])+raw.get('support_hosts',[]))),'support_hosts':raw.get('support_hosts',[]),'sample_seeds':[{'url':raw['candidate_url'],'kind':'homepage','provenance':{'method':'verified_registry','registry':file,'record':sid}}], 'ownership_evidence':raw.get('evidence',[]),'unique_products':families.get(family,{}).get('unique_products',0),'source_role':raw.get('source_role','manufacturer')})
    for d in read(ROOT/'product_tool/config/official_domains.v1.json')['domains']:
        if d['official_status']!='official_verified':continue
        existing=next((r for r in records if r['source_family']==d['source_family'] and r['official_domain'].rstrip('/')==d['url'].rstrip('/')),None)
        if existing:
            existing['allowed_hosts']=sorted(set(existing['allowed_hosts']+d['page_hosts']+d['support_hosts']));continue
        records.append({'profile_id':d['domain_id'],'source_family':d['source_family'],'brand_aliases':[d['brand']],'division':d['division'],'category_scope':d['category_scope'],'market':d['market'],'locale':d['locale'],'official_domain':d['url'],'allowed_hosts':sorted(set(d['page_hosts']+d['support_hosts'])),'support_hosts':d['support_hosts'],'sample_seeds':[{'url':d['url'],'kind':'homepage','provenance':{'method':'verified_registry','registry':'official_domains.v1.json','record':d['domain_id']}}],'ownership_evidence':d['ownership_evidence'],'unique_products':families.get(d['source_family'],{}).get('unique_products',0),'source_role':'manufacturer'})
    # Separate verified support/manual host scopes: hosts already explicitly approved,
    # never inferred sibling domains. A portal root is a registry seed, not a product URL.
    for record in list(records):
        for host in record['support_hosts']:
            if host==urlsplit(record['official_domain']).hostname or urlsplit(record['official_domain']).hostname.endswith('.'+host):continue
            url='https://'+host+'/'
            if any(r['source_family']==record['source_family'] and urlsplit(r['official_domain']).hostname==host for r in records):continue
            records.append(dict(record,profile_id=record['profile_id']+'_support_'+host.replace('.','_'),division='support_portal',official_domain=url,allowed_hosts=[host],sample_seeds=[{'url':url,'kind':'support','provenance':{'method':'verified_support_host_registry','parent_record':record['profile_id']}}]))
    seen_ids=set()
    for record in records:
        if record['profile_id'] in seen_ids:
            import hashlib
            record['profile_id'] += '_' + hashlib.sha256(record['official_domain'].encode()).hexdigest()[:6]
        seen_ids.add(record['profile_id'])
        if record['source_family'] in {'bosch_home','bosch_tools'}:
            record['unallocated_category_routed_products'] = families.get('bosch_category_routed',{}).get('unique_products',0)
            record['coverage_note'] = 'Division coverage excludes 84 category-routed products needing allocation; do not sum regional profiles.'
    priority={'jbl','samsung','lg','apple','playstation','microsoft','xbox','razer','hyperx','hiper','xiaomi_global','dreame','electrolux','electrolux_home','bosch_home'}
    records.sort(key=lambda r:(r['source_family'] not in priority,-r['unique_products'],r['profile_id']))
    # Every verified family must have a record; missing metadata is an explicit gap.
    missing=sorted(set(families)-{r['source_family'] for r in records}-({'bosch_category_routed'} if {'bosch_home','bosch_tools'} <= {r['source_family'] for r in records} else set()))
    return records,labels,families,missing,census['catalog']

def old_endpoints():
    entries=[]
    p=ROOT/'reports/source_census_2026-09-22_stage2/endpoint_results.json'
    for source in read(p)['sources']:
        for endpoint in source['endpoints']:entries.append(dict(endpoint,artifact=str(p.relative_to(ROOT)),source_record=source['source_id'],access_method='http'))
    p=ROOT/'reports/source_census_2026-09-22_stage3/endpoint_results.json'
    for source in read(p)['families']:
        for endpoint in source['endpoint_results']:entries.append(dict(endpoint,artifact=str(p.relative_to(ROOT)),source_record=source['source_family_id'],access_method='http'))
    for name in ['source_census_2026-09-22_stage7/supplemental_access.json','source_census_2026-09-22_stage7_1/access_observations.json']:
        p=ROOT/'reports'/name
        for e in read(p)['observations']:entries.append(dict(e,url=e['endpoint'],final_url=e['endpoint'],artifact=str(p.relative_to(ROOT))))
    return entries

def snapshot_cache(records):
    saved=OUTPUT/'baseline_structural_cache.json'
    if saved.exists():return read(saved)
    cache={};hosts=tuple(sorted({h for r in records for h in r['allowed_hosts']}))
    # Browser snapshots are deliberately excluded.
    for folder,name in [('source_census_2026-09-22_stage5_1','source_snapshots.sqlite3'),('source_census_2026-09-22_stage7','source_snapshots.sqlite3'),('source_census_2026-09-22_stage7_1','new_source_snapshots.sqlite3')]:
        path=ROOT/'reports'/folder/name
        with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)) as conn:
            conn.row_factory=sqlite3.Row
            for row in conn.execute('SELECT id,source_url,content,content_sha256,extracted_json FROM source_snapshots'):
                if not safe_url(row['source_url'],hosts):continue
                import hashlib
                if hashlib.sha256(row['content'].encode()).hexdigest()!=row['content_sha256']:raise ValueError('snapshot_hash_mismatch')
                metadata=json.loads(row['extracted_json']);url=metadata.get('requested_url',row['source_url'])
                structural=inspect_structure(row['content'],row['source_url'],hosts,sanitized=True)
                cache[url]={'url':url,'final_url':row['source_url'],'access_status':metadata.get('access_status','direct_access'),'protection_status':metadata.get('protection_status','unknown'),'http_status':metadata.get('http_status',200),'checked_at':metadata.get('checked_at',''),'structure':structural,'snapshot_ref':{'artifact':str(path.relative_to(ROOT)),'snapshot_id':row['id'],'sha256':row['content_sha256']},'origin':'existing_snapshot','provenance':{'method':'saved_official_snapshot','artifact':str(path.relative_to(ROOT)),'snapshot_id':row['id']},'javascript_required':metadata.get('javascript_required'), 'redirect_chain':metadata.get('redirect_chain',[])}
    write(OUTPUT/'baseline_structural_cache.json',cache)
    return cache
