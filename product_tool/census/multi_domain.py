"""Read-only official-domain fallback policy and approved dealer gate. No browser imports."""
from dataclasses import dataclass,asdict
import hashlib,json,math
from product_tool.sources import default_source_registry
from .official_domains import routed_domains

VERSION='7.0.1'
EXACT={'exact_model','exact_variant'}

@dataclass(frozen=True)
class MultiDomainBudget:
    max_domains:int=4
    max_requests_per_domain:int=10
    max_requests_per_product:int=40
    max_product_pages_per_domain:int=3
    max_sitemap_documents:int=3
    max_urls:int=800
    max_queries:int=2
    deadline_per_domain:float=40
    def __post_init__(self):
        caps={'max_domains':6,'max_requests_per_domain':12,'max_requests_per_product':60,'max_product_pages_per_domain':3,'max_sitemap_documents':5,'max_urls':2000,'max_queries':3,'deadline_per_domain':60}
        for name,cap in caps.items():
            value=getattr(self,name)
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or (name!='deadline_per_domain' and type(value) is not int) or not 0<value<=cap:raise ValueError('Invalid '+name)

def best_official(domain_results,domains):
    by_id={d.domain_id:d for d in domains};values=[]
    for result in domain_results:
        domain=by_id[result['domain_id']]
        if domain.official_status!='official_verified':continue
        for candidate in result.get('candidates',[]):
            level=candidate.get('identity_verification',{}).get('level','insufficient')
            if level=='conflict':continue
            evidence=candidate.get('identity_verification',{}).get('evidence',[])
            completeness=len({(e.get('evidence_type'),e.get('normalized_value')) for e in evidence if e.get('state')=='match'})
            rank=({'exact_variant':0,'exact_model':1,'family_only':2}.get(level,3),-completeness,domain.market_scope!='global',domain.priority,candidate['url'])
            values.append((rank,dict(candidate,domain_id=domain.domain_id,market=domain.market,evidence_completeness=completeness)))
    return min(values,key=lambda x:x[0])[1] if values else None

def dealer_gate(expected,official_result,*,market='KZ'):
    if official_result['outcome']!='official_exact_product_not_found' or not official_result.get('all_official_domains_considered'):
        return {'allowed':False,'source_id':None,'reason':'official_search_not_complete_or_exact_found'}
    source=default_source_registry().get('sulpak')
    if source.supports(expected.brand_raw,expected.category_raw,market):
        return {'allowed':True,'source_id':'sulpak','reason':'existing_LG_appliance_approval_after_bounded_official_search','approval_status':'approved_existing_scope'}
    return {'allowed':False,'source_id':None,'reason':'no_approved_dealer_for_brand_category','approval_status':'review_pending'}

class MultiDomainDiscovery:
    """A research coordinator; callers explicitly supply only an HTTP discovery executor."""
    def __init__(self,domains,executor,*,budget=None):self.domains=domains;self.executor=executor;self.budget=budget or MultiDomainBudget()
    def run(self,expected,source_family,*,research=False,checkpoint=None):
        domains=routed_domains(self.domains,expected,source_family,research=research)
        scope=hashlib.sha256(json.dumps({'version':VERSION,'identity':expected.to_dict(),'domains':[d.to_dict() for d in domains],'budget':asdict(self.budget)},sort_keys=True).encode()).hexdigest()
        if checkpoint:
            if checkpoint.get('scope')!=scope:return {'outcome':'checkpoint_incompatible','new_http_requests':0}
            if checkpoint.get('complete'):return dict(checkpoint,result_origin='checkpoint',new_http_requests=0)
            return {'outcome':'incomplete_attempt_requires_review','new_http_requests':0}
        results=[];used=0
        for domain in domains[:self.budget.max_domains]:
            if used>=self.budget.max_requests_per_product:break
            result=self.executor(domain,expected,self.budget,min(self.budget.max_requests_per_domain,self.budget.max_requests_per_product-used))
            used+=result.get('http_requests',0);results.append(result)
        from .internal_search_strategy import generate_search_queries
        query_scope_complete=any(q['reason']=='exact_seller_manufacturer_model_code' for q in generate_search_queries(expected))
        all_considered=bool(domains) and len(results)==len(domains)
        best=best_official(results,domains)
        if best and best['identity_verification'].get('level') in EXACT:outcome='official_exact_product_found'
        elif not query_scope_complete or not all_considered or any(r.get('unvalidated_candidates') for r in results):outcome='official_search_incomplete'
        elif not any(r.get('search_evidence_available') for r in results):outcome='official_search_unavailable'
        else:outcome='official_exact_product_not_found'
        result={'version':VERSION,'scope':scope,'complete':True,'source_family':source_family,'identity':expected.to_dict(),'outcome':outcome,'all_official_domains_considered':all_considered,'identity_query_scope_complete':query_scope_complete,'search_scope':'confirmed registry domains within declared budget; not proof of global absence','domains_planned':[d.domain_id for d in domains],'domains':results,'best_official':best,'http_requests':used,'new_http_requests':used,'production_ready':False,'browser_used':False}
        result['dealer_fallback']=dealer_gate(expected,result)
        return result
