"""Stage 6 source-neutral rendered search UI and structured identity contracts."""
from dataclasses import dataclass, asdict
import math
import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from product_tool.identity import IdentityVerifier, PageIdentity, VariantAttributes
from .discovery import json_ld_products, validate_structured_product_identity
from .search_routes import FLOW, private_parameter, safe_url, redact_url
from .search_results import parse_search_results, path_signals

VERSIONS={'checkpoint_schema_version':3,'strategy_version':'6.1.1','projection_version':'2','ui_detector_version':'3','result_parser_version':'browser1-stage5.1-3','ranking_version':'3','sanitizer_version':'projection2'}
SEARCH_WORD=re.compile(r'\b(?:search|поиск|іздеу|suche)\b',re.I)

@dataclass(frozen=True)
class BrowserBudget:
    max_contexts:int=1
    max_queries:int=2
    max_navigations:int=6
    max_candidates:int=3
    max_product_validations:int=3
    deadline_seconds:float=60
    max_dom_bytes:int=600000 # Legacy parser cap; never a full DOM capture limit.
    max_projection_bytes:int=120000
    max_fragment_bytes:int=12000
    max_projection_fragments:int=100
    max_network_requests:int=200
    operation_timeout_seconds:float=5
    max_technical_retries:int=1

    def __post_init__(self):
        for field,cap in [('max_contexts',1),('max_queries',2),('max_navigations',6),('max_candidates',3),('max_product_validations',3),('max_dom_bytes',1000000),('max_projection_bytes',200000),('max_fragment_bytes',20000),('max_projection_fragments',200),('max_network_requests',200)]:
            value=getattr(self,field)
            if type(value) is not int or not 1<=value<=cap:raise ValueError(field+' exceeds the Stage 6 hard cap')
        if type(self.max_technical_retries) is not int or self.max_technical_retries not in {0,1}:raise ValueError('invalid retry cap')
        if not math.isfinite(self.deadline_seconds) or not 0<self.deadline_seconds<=60:raise ValueError('invalid deadline')
        if not math.isfinite(self.operation_timeout_seconds) or not 0<self.operation_timeout_seconds<=10:raise ValueError('invalid operation timeout')


def eligibility(static_result,official_source_verified,*,expected=None,allowed_hosts=(),render_mode="interactive_search_ui"):
    if not official_source_verified:return False,'official_source_unverified'
    cp=static_result.get('checkpoint',static_result)
    evidence=static_result.get('strategy_evidence',{})
    stop=cp.get('stop_reason',static_result.get('stop_reason',''))
    # A current or historical protection/access prohibition dominates weaker outcomes.
    forbidden={'blocked','rate_limited','captcha_or_blocked','challenge_detected','foreign_redirect','login_required','access_prohibited'}
    if stop in forbidden or static_result.get('explicit_access_prohibition'):return False,'prior_access_prohibition'
    for record in cp.get('probe_results',[]):
        if record.get('http_status') in {403,429} or record.get('access_status') in forbidden or record.get('protection_status') in forbidden | {'challenge_confirmed','browser_verification_required','challenge_suspected'}:return False,'prior_protection'
    if any(r.get('allowed') is False for r in cp.get('redirect_evidence',[])):return False,'prior_foreign_redirect'
    routes=cp.get('routes',evidence.get('routes',[]))
    if any(r.get('rejection_reason') and r['rejection_reason'] not in {'query_parameter_not_declared','javascript_handler','ambiguous_query_parameter'} for r in routes):return False,'prior_unsafe_route'
    if render_mode=='render_existing_search_result':
        saved=completed_search_request(static_result,expected,allowed_hosts) if expected is not None else None
        return (True,'safe_completed_get') if saved and stop=='search_no_results' else (False,'safe_completed_get_missing')
    if render_mode!='interactive_search_ui':return False,'unknown_render_mode'
    if stop in {'search_route_not_found','search_javascript_required'}:return True,stop
    if stop=='unsafe_search_route' and routes and all(r.get('rejection_reason') in {'query_parameter_not_declared','javascript_handler'} for r in routes):return True,stop
    if stop=='search_no_results' and (evidence.get('js_search_ui') is True or any(r.get('javascript_required') is True for r in cp.get('probe_results',[]))):return True,stop
    return False,'static_outcome_not_eligible'


def detect_search_ui(html,url,allowed_hosts,*,visible_indices=None,declarative_selectors=()):
    soup=BeautifulSoup(html,'html.parser');nodes=soup.select('input,textarea,[role="searchbox"]')
    found=[];unsafe=[]
    for index,node in enumerate(nodes):
        if visible_indices is not None and index not in visible_indices:continue
        if node.has_attr('hidden') or node.has_attr('disabled') or node.get('type','').lower()=='hidden':continue
        reason=''
        form=node.find_parent('form');label=' '.join(node.get(x,'') for x in ('aria-label',))
        if node.get('id'):
            label+=' '+' '.join(x.get_text(' ',strip=True) for x in soup.find_all('label',attrs={'for':node['id']}))
        if node.find_parent('label'):label+=' '+node.find_parent('label').get_text(' ',strip=True)
        if node.get('type','').lower()=='search':reason='input_type_search'
        elif node.get('role')=='searchbox':reason='role_searchbox'
        elif SEARCH_WORD.search(label):reason='explicit_search_label'
        elif form and form.get('role')=='search':reason='form_role_search'
        elif any(node in soup.select(selector) for selector in declarative_selectors):reason='configured_search_selector'
        if not reason:continue
        action=urljoin(url,form.get('action') or url) if form else url
        method=(form.get('method') or 'GET').upper() if form else 'Enter'
        context=' '.join(str(form.get(x,'')) for x in ('action','id','class')) if form else ''
        bad=(not safe_url(action,allowed_hosts) or FLOW.search(context) or re.search(r'contact|support|newsletter',context,re.I))
        if form and (form.select('input[type="password"],input[type="file"]') or any(private_parameter(x.get('name','')) for x in form.select('input,textarea'))):bad=True
        if node.get('type','').lower() in {'password','file','email'} or private_parameter(node.get('name','')):bad=True
        if bad:unsafe.append(index);continue
        found.append({'index':index,'discovery_method':reason,'selector_description':reason,'originating_url':redact_url(url),'form_action':redact_url(action),'submit_method':method,'query_parameter':node.get('name','') if not private_parameter(node.get('name','')) else ''})
    if unsafe or len(found)>1:return None,'browser_search_ui_unsafe'
    return (found[0],'') if found else (None,'browser_search_ui_not_found')


def browser_candidates(html,**kwargs):
    soup=BeautifulSoup(html,'html.parser')
    for node in soup.select('nav,footer,header,aside,[role="navigation"]'):node.decompose()
    result=parse_search_results(str(soup),limit=20,**kwargs)
    result=tuple(c for c in result if not path_signals(c.url)[1])[:3]
    for c in result:c.strategy='browser_assisted_search'
    return result


def rendered_identity(html,*,expected,source_url):
    if json_ld_products(html):return validate_structured_product_identity(html,expected=expected,source_url=source_url)
    soup=BeautifulSoup(html,'html.parser')
    products=[n for n in soup.select('[itemscope][itemtype]') if any(v.rstrip('/').lower() in {'https://schema.org/product','http://schema.org/product'} for v in n.get('itemtype','').split())]
    values={}
    if len(products)==1:
        root=products[0]
        for field in root.select('[itemprop]'):
            nearest=field.find_parent(attrs={'itemscope':True})
            if nearest is not root:continue
            for key in field.get('itemprop','').split():
                if key in {'sku','mpn','model','color','size','storage','ram','revision','serviceIndex','region','configuration','productGroupID'}:
                    values[key]=field.get('content',field.get('value',field.get_text(' ',strip=True)))
    variants={({'revision':'hardware_revision','serviceIndex':'service_index'}.get(k,k)):v for k,v in values.items() if k in {'color','size','storage','ram','revision','serviceIndex','region','configuration'}}
    return IdentityVerifier().verify(expected,PageIdentity(manufacturer_sku=values.get('mpn',values.get('sku','')),model_code=values.get('model',''),family=values.get('productGroupID',''),variant_attributes=VariantAttributes(variants)),source=source_url,extraction_method='rendered_product_microdata')


def completed_search_request(static_result,expected,allowed_hosts):
    """Validate saved evidence, returning its exact URL. Never synthesize a request."""
    from urllib.parse import urlsplit,parse_qsl
    from .internal_search_strategy import generate_search_queries
    cp=static_result.get('checkpoint',static_result)
    queries={q['query'] for q in generate_search_queries(expected)}
    for done in cp.get('completed_queries',[]):
        url=done.get('request_url','');query=done.get('query','')
        if query not in queries or done.get('access_status')!='direct_access' or done.get('outcome') not in {'search_no_results','search_results_found'}:continue
        if not safe_url(url,allowed_hosts) or not safe_url(done.get('final_url',''),allowed_hosts):continue
        response=any(p.get('url')==url and p.get('http_status')==200 and p.get('access_status')=='direct_access' and p.get('protection_status')=='ordinary_page' and all(safe_url(u,allowed_hosts) for u in p.get('redirect_chain',[])) for p in cp.get('probe_results',[]))
        if not response:continue
        u=urlsplit(url)
        for route in cp.get('routes',[]):
            action=route.get('action_url','')
            if route.get('method')!='GET' or route.get('disposition')!='safe_get' or route.get('rejection_reason') or not safe_url(action,allowed_hosts):continue
            a=urlsplit(action);parameter=route.get('query_parameter','')
            if not parameter or private_parameter(parameter):continue
            if (u.scheme,u.netloc,u.path)!=(a.scheme,a.netloc,a.path) or u.fragment:continue
            pairs=parse_qsl(u.query,keep_blank_values=True)
            constants=[tuple(x) for x in route.get('constant_parameters',[])]
            if sorted(pairs)!=sorted(constants+[(parameter,query)]):continue
            return {'url':url,'query':query,'route_source':route.get('source',''),'evidence':'completed_static_safe_get'}
    return None


def projected_search_ui(projection):
    inputs=projection.get('inputs',[])
    if any(x.get('unsafe') for x in inputs) or len(inputs)>1:return None,'browser_search_ui_unsafe'
    return (inputs[0],'') if inputs else (None,'browser_search_ui_not_found')
