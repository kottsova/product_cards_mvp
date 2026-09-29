"""Bounded HTTP-only discovery using existing route, sitemap and identity parsers."""
from dataclasses import replace
import hashlib,json,time
from urllib.parse import urlsplit,urlunsplit,urljoin
from bs4 import BeautifulSoup
from .endpoint_probe import AccessProbe,ProbePolicy
from .models import EndpointCapability
from .search_routes import safe_url,redact_url,now
from .discovery import detect_internal_search,validate_structured_product_identity
from .internal_search_strategy import generate_search_queries
from .search_results import parse_search_results,path_signals
from .sitemap_strategy import parse_catalog_document,robots_sitemap_declarations,rank_sitemap_url,rank_candidate_url,CandidatePage
from .scoped_access import AccessLedger

class HTTPStop(Exception):pass

class HTTPDomainDiscovery:
    def __init__(self,*,probe=None,ledger=None,store=None,cache=None,offline=False):
        self.probe=probe or AccessProbe(policy=ProbePolicy(timeout_seconds=8,max_bytes=1_000_000,min_interval_seconds=1))
        self.ledger=ledger or AccessLedger();self.store=store;self.cache=cache if cache is not None else {};self.offline=offline;self.cache_refs={};self.total_requests=0
    def __call__(self,domain,expected,budget,request_limit):
        started=now();deadline=time.monotonic()+budget.deadline_per_domain;used=0;receipts=[];candidates={};errors=[];routes=[];snapshots=[];queries=[];search_available=False;truncated=False;validated=0
        hosts=domain.page_hosts+domain.support_hosts
        scope=hashlib.sha256(json.dumps({'domain':domain.domain_id,'identity':expected.to_dict()},sort_keys=True).encode()).hexdigest()
        writer=self.store.writer(expected,domain.domain_id) if self.store and not self.offline else None
        def fetch(url,method):
            nonlocal used
            if not safe_url(url,hosts):raise HTTPStop('foreign_or_unsafe_endpoint')
            cap=EndpointCapability.STRUCTURED_API if method=='structured_endpoint' else EndpointCapability.SUPPORT_PAGE if method=='support_index' else EndpointCapability.SITEMAP if method=='sitemap' else EndpointCapability.ROBOTS if method=='robots' else EndpointCapability.INTERNAL_SEARCH if method=='internal_search' else EndpointCapability.PRODUCT_PAGE if method=='product' else EndpointCapability.HOMEPAGE
            cached=url in self.cache
            if cached:response=replace(self.cache[url],capability=cap,sample_type=method)
            else:
                if self.offline:raise HTTPStop('snapshot_missing')
                def guard(target):
                    nonlocal used
                    if not safe_url(target,hosts):raise HTTPStop('foreign_or_unsafe_redirect')
                    if self.ledger.paused(target):raise HTTPStop('http_host_paused')
                    if used>=request_limit:raise HTTPStop('domain_request_budget_exhausted')
                    if time.monotonic()>=deadline:raise HTTPStop('domain_deadline_exhausted')
                    used+=1;self.total_requests+=1
                    return max(.001,deadline-time.monotonic())
                response=self.probe.probe(url,allowed_hosts=hosts,capability=cap,sample_type=method,request_guard=guard,deadline=deadline)
                self.cache[url]=response
                if writer:
                    ref=writer(response,scope)
                    if ref:self.cache_refs[url]=ref
            observation=self.ledger.record(response,discovery_method=method,domain_id=domain.domain_id)
            receipt={'requested_url':redact_url(url),'final_url':redact_url(response.final_url),'discovery_method':method,'access_method':'http','origin':'snapshot_cache' if cached else 'live_http','http_status':response.http_status,'access_status':response.access_status.value,'protection_status':response.protection_status.value,'checked_at':response.checked_at,'redirect_chain':[redact_url(u) for u in response.redirect_chain]}
            receipts.append(receipt)
            if url in self.cache_refs:snapshots.append(self.cache_refs[url])
            if response.http_status in {403,429} or response.access_status.value in {'captcha_or_blocked','rate_limited'}:raise HTTPStop('http_host_protection_stop')
            if any(not safe_url(u,hosts) for u in response.redirect_chain):raise HTTPStop('foreign_redirect')
            return response
        def usable(response):return response.access_status.value in {'direct_access','javascript_required'} and response.http_status==200
        def add_html(response):
            soup=BeautifulSoup(response.diagnostic_text,'html.parser')
            for e in soup.select('nav,header,footer,aside,[role="navigation"]'):e.decompose()
            for c in parse_search_results(str(soup),response_url=response.final_url,expected=expected,source_family=domain.source_family,allowed_hosts=hosts,limit=20):
                if path_signals(c.url)[1]:continue
                if c.url not in candidates or c.ranking_score>candidates[c.url].ranking_score:candidates[c.url]=c
        def semantic_response(response):
            if 'json' not in response.content_type:return response
            try:value=json.loads(response.diagnostic_text)
            except ValueError:return replace(response,diagnostic_text='')
            if not isinstance(value,dict) or not isinstance(value.get('@type'),str) or value.get('@type') not in {'Product','ItemList'}:return replace(response,diagnostic_text='')
            if value.get('@type')=='Product':value={'@type':'ItemList','itemListElement':[{'item':value}]}
            # Typed public JSON only; arbitrary embedded application state is not traversed.
            return replace(response,diagnostic_text='<script type="application/ld+json">'+json.dumps(value).replace('<','\\u003c')+'</script>')
        stop='bounded_discovery_complete'
        try:
            home=fetch(domain.url,'catalog_index')
            if usable(home):
                add_html(home)
                routes=list(detect_internal_search(home.diagnostic_text,home.final_url,allowed_hosts=hosts,configured_endpoints=domain.capabilities.get('configured_search',())))
                search_available=bool(candidates)
            # Search first when declared; no synthetic route or model product URL.
            executable=next((r for r in routes if r.executable),None)
            if executable:
                for q in generate_search_queries(expected)[:budget.max_queries]:
                    response=fetch(executable.query_url(q['query']),'internal_search');queries.append(q['query'])
                    if usable(response):add_html(response);search_available=True
                    if any('exact_model_in_result' in ' '.join(c.ranking_reasons) for c in candidates.values()):break
            root=urlsplit(domain.url);robots_url=urlunsplit((root.scheme,root.netloc,'/robots.txt','',''))
            robots=fetch(robots_url,'robots')
            maps=list(robots_sitemap_declarations(robots.diagnostic_text)) if usable(robots) else []
            maps+=domain.capabilities.get('sitemap_urls',[])
            region=root.path.strip('/').split('/')[0]
            def map_rank(u):return (0 if region and region in urlsplit(u).path else 1,-rank_sitemap_url(u)[0],u)
            pending=[(u,0) for u in sorted(set(maps),key=map_rank) if safe_url(u,hosts)];seen=set();url_count=0
            while pending and len(seen)<budget.max_sitemap_documents:
                u,depth=pending.pop(0)
                if u in seen:continue
                seen.add(u);response=fetch(u,'sitemap')
                if not usable(response):continue
                try:kind,locations,cut=parse_catalog_document(response.diagnostic_text,max_urls=budget.max_urls-url_count)
                except ValueError:errors.append('invalid_sitemap:'+redact_url(u));continue
                search_available=True;truncated|=cut
                if kind=='sitemapindex':
                    if depth>=2:truncated=True;continue
                    pending.extend((v,depth+1) for v in sorted(locations,key=map_rank) if safe_url(v,hosts) and v not in seen)
                    continue
                url_count+=len(locations)
                for location in locations:
                    score,reasons,categories,models=rank_candidate_url(location,expected=expected,source_family=domain.source_family,allowed_hosts=hosts,sitemap_url=u,category_hints=(expected.category_raw,))
                    if not models or path_signals(location)[1]:continue
                    c=CandidatePage(location,'',domain.source_family,'sitemap_catalog',score,reasons,categories,models,({'type':'sitemap_loc','sitemap_url':u},))
                    if c.url not in candidates:candidates[c.url]=c
                if url_count>=budget.max_urls:truncated=True;break
            truncated|=bool(pending)
            for endpoint in domain.capabilities.get('structured_endpoints',[])[:1]:
                response=fetch(endpoint,'structured_endpoint')
                if usable(response):
                    semantic=semantic_response(response)
                    if semantic.diagnostic_text:add_html(semantic);search_available=True
            for endpoint in domain.capabilities.get('support_indexes',[])[:1]:
                response=fetch(endpoint,'support_index')
                if usable(response):add_html(response);search_available=True
            for index in domain.capabilities.get('catalog_indexes',[])[:1]:
                response=fetch(index,'catalog_index')
                if usable(response):add_html(response);search_available=True
        except HTTPStop as exc:stop=str(exc)
        # Never navigate candidates after protection, missing replay or an exhausted budget.
        ordered=sorted(candidates.values(),key=lambda c:(-c.ranking_score,c.url))[:20]
        if stop=='bounded_discovery_complete':
            for candidate in ordered[:budget.max_product_pages_per_domain]:
                try:
                    response=fetch(candidate.url,'product');validated+=1
                    candidate.final_url=redact_url(response.final_url);candidate.access_status=response.access_status.value;candidate.protection_status=response.protection_status.value
                    if usable(response):candidate.identity_verification=validate_structured_product_identity(response.diagnostic_text,expected=expected,source_url=response.final_url).to_dict()
                    else:candidate.rejection_reason='target_unavailable'
                except HTTPStop as exc:stop=str(exc);break
        for c in ordered:
            if not c.identity_verification and not c.rejection_reason:c.rejection_reason='not_validated_within_budget'
        return {'domain_id':domain.domain_id,'url':domain.url,'market':domain.market,'division':domain.division,'outcome':stop,'http_requests':used,'requests':receipts,'candidates':[c.to_dict() for c in ordered],'routes':[r.to_dict() for r in routes],'queries':queries,'errors':errors,'snapshots':snapshots,'search_evidence_available':search_available,'unvalidated_candidates':any(c.rejection_reason=='not_validated_within_budget' for c in ordered),'truncated':truncated,'product_validations':validated,'started_at':started,'last_checked_at':now(),'browser_used':False}
