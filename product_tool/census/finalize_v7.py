"""Rebuild final decisions from observations; add one clean-code Samsung catalog sample."""
from pathlib import Path
from dataclasses import replace
import json
from .runner_v7 import ROOT,OUTPUT
from .runner_v5 import write_json
from .official_domains import load_domains
from .multi_domain import MultiDomainDiscovery,MultiDomainBudget
from .http_domain_discovery import HTTPDomainDiscovery
from .endpoint_probe import ProbeResult
from .models import AccessStatus,ProtectionStatus,EndpointCapability
from .scoped_access import AccessLedger,AccessObservation
from .search_snapshots import SearchSnapshotStore
from .catalog import load_catalog_coverage
from product_tool.identity import ProductIdentity

def load_cache(store):
    saved=json.loads((OUTPUT/'http_cache.json').read_text(encoding='utf-8'));cache={};refs={}
    for url,row in saved.items():
        data=dict(row['response']);data['access_status']=AccessStatus(data['access_status']);data['protection_status']=ProtectionStatus(data['protection_status']);data['capability']=EndpointCapability(data['capability']);data['fingerprints']=()
        if row['snapshot']:
            snapshot=store.load(row['snapshot']);data['diagnostic_text']=snapshot['content'];refs[url]=row['snapshot']
        else:data['diagnostic_text']=''
        cache[url]=ProbeResult(**data)
    return cache,refs

def execute():
    final_path=OUTPUT/'final_results.json'
    if final_path.exists():return json.loads(final_path.read_text(encoding='utf-8'))
    observed=json.loads((OUTPUT/'dry_run.json').read_text(encoding='utf-8'));domains=load_domains();budget=MultiDomainBudget();runs=[]
    samples={(family,e.seller_sku):e for family,e,_ in __import__('product_tool.census.runner_v7',fromlist=['samples']).samples()}
    for row in observed['runs']:
        expected=samples[(row['source_family'],row['identity']['seller_sku'])];by_id={r['domain_id']:r for r in row['domains']}
        coordinator=MultiDomainDiscovery(domains,lambda d,*a:dict(by_id[d.domain_id],http_requests=0),budget=budget)
        stale=coordinator.run(expected,row['source_family'],research=True,checkpoint=row)
        result=coordinator.run(expected,row['source_family'],research=True)
        result['observed_http_requests']=row['http_requests'];result['observed_outcome']=row['outcome'];result['old_checkpoint_outcome']=stale['outcome'];result['result_origin']='offline_policy_reprocessing'
        if 'dealer_discovery' in row:result['dealer_discovery']=row['dealer_discovery']
        result['resume_verification']={'new_http_requests':coordinator.run(expected,row['source_family'],research=True,checkpoint=result)['new_http_requests']}
        runs.append(result)
    # Third Samsung sample is selected by catalog coverage, not an externally found product page.
    supplemental=OUTPUT/'supplemental_samsung.json'
    if supplemental.exists():result=json.loads(supplemental.read_text(encoding='utf-8'))
    else:
        marker=OUTPUT/'supplemental_attempt.json'
        if marker.exists():raise RuntimeError('Supplemental attempt needs offline recovery')
        c=load_catalog_coverage(ROOT/'data/catalog_2026-09-21_filtered.xlsx')
        category=max((x for x in c.coverages if x.brand=='Samsung' and x.category_group=='major_home_appliances'),key=lambda x:x.unique_products)
        sku=category.sample_seller_skus[0];expected=ProductIdentity.from_product({'brand':'Samsung','category':category.category,'name':sku,'search_code':sku,'model_candidates':[sku]})
        store=SearchSnapshotStore(OUTPUT/'source_snapshots.sqlite3');cache,refs=load_cache(store)
        evidence=json.loads((OUTPUT/'access_observations.json').read_text(encoding='utf-8'));ledger=AccessLedger([AccessObservation(**x) for x in evidence['observations']])
        ledger.paused_hosts={(x['host'],x['access_method']):AccessObservation(**x) for x in evidence['run_host_pauses']}
        http=HTTPDomainDiscovery(store=store,cache=cache,ledger=ledger);http.cache_refs=refs
        write_json(marker,{'identity':expected.to_dict(),'reason':'third catalog sample with complete canonical query; no browser'})
        result=MultiDomainDiscovery(domains,http,budget=budget).run(expected,'samsung',research=True)
        result['result_origin']='supplemental_live_http';write_json(supplemental,result)
        write_json(OUTPUT/'supplemental_access.json',ledger.to_dict())
        write_json(OUTPUT/'supplemental_cache.json',{url:{'response':r.to_dict(),'snapshot':http.cache_refs.get(url)} for url,r in http.cache.items()})
    runs.append(result)
    payload={'version':'7.0.1','runs':runs,'initial_http_requests':observed['http_requests'],'supplemental_http_requests':result['http_requests'],'chromium_launches':0,'note':'initial observations preserved; decisions rebuilt offline; third Samsung sample avoids partial composite query'}
    write_json(final_path,payload);return payload

if __name__=='__main__':execute()
