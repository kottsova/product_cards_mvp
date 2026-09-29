"""Explicit Stage 7 pilot: ten catalog products, HTTP only, no production integration."""
from dataclasses import asdict
from pathlib import Path
import hashlib,json,sys
from product_tool.identity import ProductIdentity
from product_tool.sources import default_source_registry
from .catalog import load_catalog_coverage
from .official_domains import load_domains,OfficialDomain
from .multi_domain import MultiDomainDiscovery,MultiDomainBudget
from .http_domain_discovery import HTTPDomainDiscovery
from .search_snapshots import SearchSnapshotStore
from .scoped_access import AccessLedger,AccessObservation
from .runner_v5 import write_json

ROOT=Path(__file__).resolve().parents[2]
OUTPUT=ROOT/'reports/source_census_2026-09-22_stage7'

def samples():
    catalog=load_catalog_coverage(ROOT/'data/catalog_2026-09-21_filtered.xlsx')
    for family,brand in [('lg','LG'),('bosch_home','BOSCH'),('samsung','Samsung'),('karcher','Karcher'),('dreame','Dreame')]:
        categories=sorted((c for c in catalog.coverages if c.brand==brand),key=lambda c:(-c.unique_products,c.category))
        # Two distinct high-coverage categories; avoid composite seller/marketplace codes.
        chosen=[]
        for category in categories:
            if family=='bosch_home' and category.category_group not in {'major_home_appliances','small_home_appliances'}:continue
            codes=[sku for sku in category.sample_seller_skus if not (sku[:1].isdigit() and any(c.isalpha() for c in sku))]
            if not codes:continue
            sku=codes[0]
            expected=ProductIdentity.from_product({'brand':brand,'category':category.category,'name':sku,'search_code':sku,'model_candidates':[sku]})
            chosen.append((expected,category.unique_products))
            if len(chosen)==2:break
        if len(chosen)!=2:raise ValueError('Insufficient catalog samples '+family)
        for expected,coverage in chosen:yield family,expected,coverage

def execute():
    OUTPUT.mkdir(exist_ok=True)
    if (OUTPUT/'dry_run.json').exists():return json.loads((OUTPUT/'dry_run.json').read_text(encoding='utf-8'))
    cp_path=OUTPUT/'checkpoint.json';checkpoint=json.loads(cp_path.read_text(encoding='utf-8')) if cp_path.exists() else {}
    markers_path=OUTPUT/'http_attempts.json';markers=json.loads(markers_path.read_text(encoding='utf-8')) if markers_path.exists() else {}
    domains=load_domains();budget=MultiDomainBudget();store=SearchSnapshotStore(OUTPUT/'source_snapshots.sqlite3')
    # Historical browser observation is retained as endpoint evidence only, never an HTTP pause.
    prior=AccessObservation('www.lg.com','https://www.lg.com/kz/search?q=27ART10AKPL','browser','render_existing_search_result','captcha_or_blocked','challenge_detected',None,'2026-09-22T15:52:04+00:00','lg_kz')
    ledger=AccessLedger([prior]);http=HTTPDomainDiscovery(ledger=ledger,store=store)
    def save_cache():
        write_json(OUTPUT/'http_cache.json',{url:{'response':r.to_dict(),'snapshot':http.cache_refs.get(url)} for url,r in http.cache.items()})
        write_json(OUTPUT/'access_observations.json',ledger.to_dict())
    def execute_domain(domain,expected,budget,limit):
        r=http(domain,expected,budget,limit);save_cache()
        print(domain.domain_id,expected.seller_sku,r['outcome'],'HTTP',r['http_requests'],'candidates',len(r['candidates']),flush=True)
        return r
    coordinator=MultiDomainDiscovery(domains,execute_domain,budget=budget);runs=[]
    for family,expected,coverage in samples():
        key=family+':'+expected.seller_sku
        if key in checkpoint:
            runs.append(checkpoint[key]);continue
        if key in markers:raise RuntimeError('Incomplete attempt requires offline recovery: '+key)
        markers[key]={'identity':expected.to_dict(),'status':'started'};write_json(markers_path,markers)
        result=coordinator.run(expected,family,research=True)
        if result['dealer_fallback']['allowed']:
            approved=default_source_registry().get('sulpak')
            dealer=OfficialDomain('sulpak','lg','LG','https://www.sulpak.kz/','KZ','ru-KZ','regional','approved_LG_appliances',('*',),({'type':'existing_policy_approval','url':'product_tool/config/source_catalog.v2.json'},),('www.sulpak.kz',),(),('www.sulpak.kz',),{},100,official_status='third_party_confirmed')
            result['dealer_discovery']=execute_domain(dealer,expected,budget,6)
        resume=coordinator.run(expected,family,research=True,checkpoint=result)
        result['resume_verification']={'new_http_requests':resume['new_http_requests'],'outcome':resume['outcome']}
        result['category_catalog_coverage']=coverage
        checkpoint[key]=result;write_json(cp_path,checkpoint);runs.append(result)
        write_json(OUTPUT/'partial_runs.json',{'runs':runs})
    before=json.loads((OUTPUT/'protected_hashes_before.json').read_text(encoding='utf-8'));after={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in before}
    write_json(OUTPUT/'protected_hashes_after.json',after);assert before==after,'Protected baseline changed'
    forbidden=[name for name in sys.modules if name.startswith(('playwright','selenium','product_tool.census.browser'))]
    assert not forbidden,'Browser module imported by HTTP pilot'
    payload={'version':'7.0','budget':asdict(budget),'runs':runs,'http_requests':http.total_requests,'browser_modules_loaded':forbidden,'chromium_launches':0,'production_registry_unchanged':True,'registry_snapshot':[d.to_dict() for d in domains],'sample_policy':'first non-composite sample SKU from each of two highest-coverage eligible categories; no handpicked product URLs','ownership_research':'official selectors/corporate pages; separate web research, not product discovery'}
    write_json(OUTPUT/'dry_run.json',payload);save_cache();return payload

if __name__=='__main__':execute()
