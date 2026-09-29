"""Opt-in bounded browser-assisted first-party search. No production integration."""
from dataclasses import asdict
import hashlib
import json
import re
import time
from bs4 import BeautifulSoup
from .browser_contracts import BrowserBudget,VERSIONS,eligibility,projected_search_ui,completed_search_request,browser_candidates,rendered_identity
from .browser_projection import projection_html,validate_projection
from .browser_runtime import BrowserRuntime,BrowserFailure,PlaywrightBrowser,discover_runtime
from .internal_search_strategy import generate_search_queries
from .search_routes import safe_url,redact_url,now
from .sitemap_strategy import StrategyResult,BudgetUsage,CandidatePage,normalize_candidate_url

OUTCOMES={'render_existing_search_started','interactive_search_started','search_projection_empty','projection_budget_exhausted','network_budget_exhausted','browser_runtime_unavailable','browser_search_ui_not_found','browser_search_ui_unsafe','browser_search_submitted','browser_no_results','browser_candidates_found','browser_exact_model_found','browser_exact_variant_found','browser_identity_insufficient','browser_identity_conflict','browser_javascript_error','interaction_blocked','challenge_detected','foreign_redirect','budget_exhausted','deadline_exhausted','checkpoint_complete','checkpoint_incompatible','snapshot_missing','browser_assisted_disabled','browser_strategy_not_eligible'}


class BrowserAssistedSearchStrategy:
    strategy_id='browser_assisted_search'
    def __init__(self,*,budget=None,runtime=None,browser_factory=None,clock=time.monotonic):
        self.budget=budget or BrowserBudget();self.runtime=runtime;self.factory=browser_factory;self.clock=clock

    def run(self,*,source_family,source_url,allowed_hosts,expected,static_result,official_source_verified=False,browser_assisted=False,declarative_selectors=(),render_mode="interactive_search_ui",checkpoint=None,reprocess=False,snapshot_writer=None,snapshot_loader=None,checkpoint_callback=None):
        started=now();start=self.clock();deadline=start+self.budget.deadline_seconds
        prior=dict(checkpoint or {});candidates=[];refs=[];actions=[];events=[];errors=[];ui_evidence=[];counts={'contexts':0,'queries':0,'navigations':0,'product_validations':0,'network_requests':0,'technical_retries':0,'document_requests':0,'script_xhr_fetch_requests':0,'stylesheet_requests':0,'other_requests':0,'resource_attempts':0,'blocked_requests':0,'blocked_image_requests':0,'blocked_font_requests':0,'blocked_media_requests':0,'blocked_download_requests':0};runtime=self.runtime
        def result(stop,cp=None):
            cp=cp if cp is not None else {**versions,'strategy':self.strategy_id,'render_mode':render_mode,'scope_key':scope,'compatibility_key':key,'status':'complete' if stop!='snapshot_missing' else 'incomplete','stop_reason':stop,'candidates':[c.to_dict() for c in candidates],'snapshots':refs,'counts':counts,'ui_evidence':ui_evidence,'actions':actions,'events':events,'errors':errors,'started_at':started,'finished_at':now()}
            if checkpoint_callback:checkpoint_callback(cp)
            usage=BudgetUsage(http_requests=counts['network_requests'],search_queries=counts['queries'],product_pages=counts['product_validations'])
            return StrategyResult(source_family,tuple(candidates),usage,(),(),tuple(errors),stop in {'budget_exhausted','deadline_exhausted','projection_budget_exhausted','network_budget_exhausted'},stop,cp,started,now(),strategy=self.strategy_id,strategy_evidence={'versions':versions,'render_mode':render_mode,'saved_search_request':saved_request,'browser_usage':counts,'actions':actions,'ui_evidence':ui_evidence,'events':events,'production_ready':False,'processing_mode':'snapshot_reprocessing' if reprocess else 'browser'})
        saved_request=completed_search_request(static_result,expected,allowed_hosts) if render_mode=='render_existing_search_result' else None
        scope=hashlib.sha256(json.dumps({'source_family':source_family,'source_url':source_url,'allowed_hosts':sorted(allowed_hosts),'identity':expected.to_dict(),'selectors':declarative_selectors,'render_mode':render_mode,'saved_search_request':saved_request},sort_keys=True).encode()).hexdigest()
        versions={**VERSIONS,'browser_runtime_version':runtime.runtime_version if runtime else 'not_checked','browser_version':runtime.browser_version if runtime else 'not_checked'};key=''
        if not browser_assisted and not reprocess:return result('browser_assisted_disabled')
        allowed,reason=eligibility(static_result,official_source_verified,expected=expected,allowed_hosts=allowed_hosts,render_mode=render_mode)
        if not allowed:errors.append(reason);return result('browser_strategy_not_eligible')
        if not safe_url(source_url,allowed_hosts):return result('foreign_redirect')
        static_cp=static_result.get('checkpoint',static_result)
        if any(not safe_url(url,allowed_hosts) for r in static_cp.get('redirect_evidence',[]) for url in r.get('chain',[])):
            errors.append('prior_foreign_redirect');return result('browser_strategy_not_eligible')
        if runtime is None:
            if reprocess:runtime=BrowserRuntime(False,runtime_version=prior.get('browser_runtime_version','unavailable'),browser_version=prior.get('browser_version','unavailable'))
            else:runtime=discover_runtime()
        versions={**VERSIONS,'browser_runtime_version':runtime.runtime_version,'browser_version':runtime.browser_version}
        key=hashlib.sha256(json.dumps({'scope':scope,'versions':versions,'budget':asdict(self.budget)},sort_keys=True).encode()).hexdigest()
        if prior and prior.get('scope_key')!=scope:return result('checkpoint_incompatible',prior)
        compatible=prior.get('compatibility_key')==key and all(prior.get(k)==v for k,v in versions.items())
        if prior and not compatible and not reprocess:return result('checkpoint_incompatible',prior)
        if prior and compatible and not reprocess:
            if prior.get('status')=='complete':
                candidates=[CandidatePage.from_dict(c) for c in prior.get('candidates',[])];return result('checkpoint_complete',prior)
            return result('snapshot_missing',prior) # Never silently repeat an incomplete browser run.
        replay={}
        if reprocess:
            try:
                refs=list(prior.get('snapshots',[]))
                if not refs or snapshot_loader is None:raise ValueError('snapshot_missing')
                for ref in refs:
                    saved=snapshot_loader(ref);meta=saved['extracted']
                    if meta['identity_key']!=scope or hashlib.sha256(saved['content'].encode()).hexdigest()!=ref['content_sha256']:raise ValueError('snapshot_hash_or_scope_mismatch')
                    if meta.get('projection_version')!=VERSIONS['projection_version'] or meta.get('render_mode')!=render_mode:raise ValueError('projection_version_or_mode_mismatch')
                    replay[(meta['phase'],meta['query'],normalize_candidate_url(meta.get('requested_url',saved['source_url']))) ]={'url':saved['source_url'],'projection':json.loads(saved['content']),'javascript_errors':meta.get('javascript_errors',0),'counts':{}}
            except (ValueError,KeyError,OSError) as exc:errors.append(str(exc));return result('snapshot_missing')
        elif not runtime.available:return result('browser_runtime_unavailable')
        if not reprocess and render_mode=='interactive_search_ui':
            routes=static_result.get('checkpoint',static_result).get('routes',[])
            if not any(r.get('action_url')==source_url and not r.get('query_parameter') and r.get('rejection_reason') in {'query_parameter_not_declared','javascript_handler'} and safe_url(r.get('action_url',''),allowed_hosts) for r in routes):
                errors.append('verified_search_ui_page_required');return result('browser_strategy_not_eligible')
        driver=None;last_state=None
        def check(state):
            if self.clock()>=deadline:raise BrowserFailure('deadline_exhausted')
            if not safe_url(state['url'],allowed_hosts):raise BrowserFailure('foreign_redirect')
            try:validate_projection(state['projection'],self.budget)
            except ValueError as exc:raise BrowserFailure(str(exc))
            if state.get('http_status') in {403,429} or any(s in {403,429} for s in state.get('network_statuses',[])) or state.get('protection') or state['projection'].get('protection'):
                raise BrowserFailure('challenge_detected')
            for name,value in state.get('counts',{}).items():
                if name in counts and not reprocess:counts[name]=value
            if counts['network_requests']>self.budget.max_network_requests:raise BrowserFailure('network_budget_exhausted')
            if counts['navigations']>self.budget.max_navigations:raise BrowserFailure('budget_exhausted')
        def call(command,**kwargs):
            if self.clock()>=deadline:raise BrowserFailure('deadline_exhausted')
            if command in {'goto','submit'} and counts['navigations']>=self.budget.max_navigations:raise BrowserFailure('budget_exhausted')
            # Only idempotent observation/navigation can retry; never double-submit.
            try:return driver.call(command,**kwargs)
            except BrowserFailure as exc:
                if str(exc)!='browser_javascript_error' or command not in {'goto','state'} or counts['technical_retries']>=self.budget.max_technical_retries:raise
                probe=driver.call('state');check(probe)
                counts['technical_retries']+=1
                return driver.call(command,**kwargs)
        def obtain(phase,query='',url=None,ui=None):
            nonlocal last_state
            if reprocess:
                matches=[s for (p,q,u),s in replay.items() if p==phase and q==query and (url is None or u==normalize_candidate_url(url) or phase=='homepage')]
                if not matches:raise BrowserFailure('snapshot_missing')
                state=matches[0]
            else:
                state=call('submit',query=query,ui=ui,declarative_selectors=declarative_selectors) if phase=='search' else call('goto',url=url,render_mode=render_mode,queries=[q['query'] for q in generate_search_queries(expected)])
            check(state)
            state['render_mode']=render_mode;state['versions']=versions;state['requested_url']=url or state['url']
            if state.get('cookie_banner') or state['projection'].get('cookie_dialog',{}).get('visible'):
                if reprocess:raise BrowserFailure('interaction_blocked')
                try:state=call('dismiss_cookies')
                except BrowserFailure:
                    if snapshot_writer:refs.append(snapshot_writer(state,phase,query,scope))
                    raise
                state['render_mode']=render_mode;state['versions']=versions;state['requested_url']=url or state['url']
                actions.append({'action':'reject_optional_cookies'});check(state)
                state['render_mode']=render_mode;state['versions']=versions;state['requested_url']=url or state['url']
            if state.get('cookie_banner') or state['projection'].get('cookie_dialog',{}).get('visible'):raise BrowserFailure('interaction_blocked')
            last_state=state
            actions.append({'action':'submit_search' if phase=='search' else 'open_'+phase,'url':redact_url(state['url']),'query':query,'elapsed_seconds':round(self.clock()-start,3)})
            if snapshot_writer and not reprocess:refs.append(snapshot_writer(state,phase,query,scope))
            return state
        stop='search_projection_empty'
        try:
            if not reprocess:
                driver=self.factory(runtime,self.budget,allowed_hosts) if self.factory else PlaywrightBrowser(runtime,self.budget,allowed_hosts)
                try:
                    startup=driver.start()
                    if isinstance(startup,dict) and startup.get('runtime_version') and startup['runtime_version']!=runtime.browser_version:raise BrowserFailure('browser_runtime_unavailable')
                except (BrowserFailure,OSError):raise BrowserFailure('browser_runtime_unavailable')
                counts['contexts']=1
            def parse_candidates(state):
                return list(browser_candidates(projection_html(state['projection']),response_url=state['url'],expected=expected,source_family=source_family,allowed_hosts=allowed_hosts,max_bytes=self.budget.max_dom_bytes))[:self.budget.max_candidates]
            if render_mode=='render_existing_search_result':
                events.append('render_existing_search_started')
                state=obtain('existing_search',query=saved_request['query'],url=saved_request['url'])
                candidates=parse_candidates(state)
            else:
                events.append('interactive_search_started')
                state=obtain('homepage',url=source_url)
                queries=generate_search_queries(expected)
                selected=list(queries[:1])+[q for q in queries[1:] if q['reason'].startswith('remove_spaces')][:1]
                if not selected:raise BrowserFailure('browser_search_ui_not_found')
                for query_index,q in enumerate(selected[:self.budget.max_queries]):
                    if not reprocess:state=call('state');check(state)
                    ui,outcome=projected_search_ui(state['projection'])
                    if outcome=='browser_search_ui_not_found' and query_index:break
                    if outcome:raise BrowserFailure(outcome)
                    ui_evidence.append({k:v for k,v in ui.items() if k!='index'}|{'render_elapsed_seconds':round(self.clock()-start,3)})
                    if not reprocess:counts['queries']+=1
                    state=obtain('search',query=q['query'],ui=ui)
                    events.append('browser_search_submitted')
                    candidates=parse_candidates(state)
                    if candidates:break
            if candidates:events.append('browser_candidates_found')
            for candidate in candidates[:self.budget.max_product_validations]:
                state=obtain('product',url=candidate.url)
                if not reprocess:counts['product_validations']+=1
                candidate.final_url=redact_url(state['url']);candidate.access_status='direct_access'
                verification=rendered_identity(projection_html(state['projection']),expected=expected,source_url=candidate.final_url)
                candidate.identity_verification=verification.to_dict()
                if verification.level.value=='exact_variant' or (verification.level.value=='exact_model' and not expected.variant_attributes.values):break
            levels={c.identity_verification.get('level') for c in candidates}
            if 'exact_variant' in levels:stop='browser_exact_variant_found'
            elif 'exact_model' in levels:stop='browser_exact_model_found'
            elif 'conflict' in levels:stop='browser_identity_conflict'
            elif candidates:stop='browser_identity_insufficient'
            # JavaScript errors are diagnostics, not evidence that a valid projection failed.
        except BrowserFailure as exc:
            stop=str(exc)
            for name,value in exc.counts.items():
                if name in counts and not reprocess:counts[name]=value
        finally:
            if driver:
                driver.close();actions.append({'action':'close_context','closed':True})
                for name,value in getattr(driver,'counts',{}).items():
                    if name in counts:counts[name]=value
        if not candidates and stop=='search_projection_empty':events.append(stop)
        return result(stop)
