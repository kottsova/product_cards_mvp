"""Isolated Playwright worker. JSON lines protocol; never uses a persistent profile."""
import json
import re
import sys
import time
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright
from pathlib import Path
from browser_resources import admit_resource
PROJECTION_SCRIPT=Path(__file__).with_name("browser_projection.js").read_text(encoding="utf-8-sig")

p=browser=context=page=None
policy={};deadline=0;signal='';counts={'contexts':0,'navigations':0,'network_requests':0,'blocked_requests':0};pending=[];last_url='about:blank';js_errors=0

def allowed(url):
    try:
        parsed=urlsplit(url);host=(parsed.hostname or '').lower()
        return not parsed.username and not parsed.password and parsed.port in {None,80,443} and parsed.scheme in {'http','https'} and any(host==h or host.endswith('.'+h) for h in policy['allowed_hosts'])
    except ValueError:return False

def timeout():
    if time.monotonic()>=deadline:raise RuntimeError('deadline_exhausted')
    return max(1,min(policy['operation_timeout_seconds'],deadline-time.monotonic())*1000)

def guard():
    if signal:raise RuntimeError(signal)
    timeout()
    if page and page.url!='about:blank' and not allowed(page.url):
        counts['last_blocked_host']=(urlsplit(page.url).hostname or '')
        raise RuntimeError('foreign_redirect')
    if page and page.url!='about:blank':
        protected=page.evaluate(PROJECTION_SCRIPT,dict(policy,inspect_only=True)).get('protection',False)
        if protected:raise RuntimeError('challenge_detected')

def routed(route):
    global signal
    request=route.request
    nav=request.is_navigation_request() and request.frame==page.main_frame
    if signal or time.monotonic()>=deadline:
        signal=signal or 'deadline_exhausted';counts['blocked_requests']+=1;route.abort();return
    if not allowed(request.url):
        if nav:
            signal='foreign_redirect'
            counts['last_blocked_host']=(urlsplit(request.url).hostname or '')
        counts['blocked_requests']+=1;route.abort();return
    path=urlsplit(request.url).path.lower()
    if re.search(r'/(?:login|register|account|cart|checkout|contact)(?:[/.]|$)',path):
        if nav:signal='interaction_blocked'
        counts['blocked_requests']+=1;route.abort();return
    if request.method not in {'GET','HEAD'} and not (request.method=='POST' and 'search' in path):
        counts['blocked_requests']+=1;route.abort();return
    if nav:
        if counts['navigations']>=policy['max_navigations']:
            signal='budget_exhausted';counts['blocked_requests']+=1;route.abort();return
        counts['navigations']+=1;pending.append(request.url)
    admission=admit_resource(counts,request.resource_type,path,policy['max_network_requests'])
    if admission!='allowed':
        if admission=='network_budget_exhausted':
            counts['capped_requests']=counts.get('capped_requests',0)+1
            # A search result document may already be readable. Block surplus
            # subresources within the same cap, then inspect its DOM instead of
            # discarding the whole navigation. A capped document still fails.
            if nav or policy.get('render_mode')!='render_existing_search_result':
                signal=admission
        counts['blocked_requests']+=1;route.abort();return
    route.continue_()

def response_event(response):
    global signal
    if allowed(response.url) and response.status == 403:signal='challenge_detected'
    if allowed(response.url) and response.status == 429:
        counts['rate_limit_url']=response.url
        signal='rate_limited'

def frame_event(frame):
    global signal,last_url
    if frame!=page.main_frame or frame.url=='about:blank':return
    if not allowed(frame.url):
        signal='foreign_redirect'
        counts['last_blocked_host']=(urlsplit(frame.url).hostname or '')
        return
    if frame.url!=last_url:
        if frame.url in pending:pending.remove(frame.url)
        else:
            if counts['navigations']>=policy['max_navigations']:signal='budget_exhausted'
            else:counts['navigations']+=1
        last_url=frame.url

def cookie_dialogs():
    return [x for x in page.locator('[role="dialog"],#onetrust-banner-sdk,.cookie-banner').all()[:10] if x.is_visible() and re.search(r'cookie|cookies|куки',x.inner_text(timeout=timeout()),re.I)]

def state():
    guard()
    projection=page.evaluate(PROJECTION_SCRIPT,policy)
    if projection.get('overflow'):raise RuntimeError('projection_budget_exhausted')
    if projection.get('protection'):raise RuntimeError('challenge_detected')
    return {'url':page.url,'projection':projection,'cookie_banner':projection['cookie_dialog']['visible'],'counts':dict(counts),'javascript_errors':js_errors}

def command(cmd):
    global p,browser,context,page,deadline,policy,js_errors
    kind=cmd['command']
    if kind=='start':
        policy=cmd['policy'];deadline=time.monotonic()+policy['deadline_seconds']
        p=sync_playwright().start();browser=p.chromium.launch(headless=True,timeout=timeout())
        context=browser.new_context(service_workers='block',accept_downloads=False)
        page=context.new_page();counts['contexts']=1
        context.route('**/*',routed);page.on('response',response_event);page.on('framenavigated',frame_event)
        def page_error(error):
            global js_errors
            js_errors+=1
        page.on('pageerror',page_error)
        def download(item):
            global signal
            counts['blocked_download_requests']=counts.get('blocked_download_requests',0)+1
            signal='interaction_blocked';item.cancel()
        page.on('download',download)
        def popup(other):
            global signal
            if other!=page:signal='interaction_blocked';other.close()
        context.on('page',popup)
        page.set_default_timeout(timeout());page.set_default_navigation_timeout(timeout())
        return {'runtime_version':browser.version,'counts':dict(counts)}
    if kind=='close':
        if context:context.close()
        if browser:browser.close()
        if p:p.stop()
        return {'closed':True,'counts':dict(counts)}
    guard()
    if kind=='goto':
        policy['queries']=cmd.get('queries',[])
        policy['search_result_hosts']=cmd.get('search_result_hosts',[])
        policy['render_mode']=cmd.get('render_mode','interactive_search_ui')
        if not allowed(cmd['url']):raise RuntimeError('foreign_redirect')
        page.goto(cmd['url'],wait_until='domcontentloaded',timeout=timeout())
        # Fixed bounded render opportunity, never networkidle.
        page.wait_for_timeout(min(600,timeout()))
        return state()
    if kind=='state':return state()
    if kind=='document_snapshot':
        # Opt-in read-only capture of an already admitted public document.
        # The same challenge, host, navigation and DOM budgets apply.
        if policy.get('render_mode')!='render_existing_search_result':raise RuntimeError('interaction_blocked')
        result=state()
        content=page.content()
        if len(content.encode('utf-8'))>policy['max_dom_bytes']:raise RuntimeError('projection_budget_exhausted')
        result['html']=content
        return result
    if kind=='dismiss_cookies':
        dialogs=cookie_dialogs();buttons=[]
        for dialog in dialogs:
            for text in ('Reject all','Reject All','Only necessary','Continue without accepting','Отклонить все','Только необходимые'):
                locator=dialog.get_by_role('button',name=text,exact=True)
                if locator.count()==1 and locator.is_visible():buttons.append(locator)
        if len(buttons)!=1:raise RuntimeError('interaction_blocked')
        buttons[0].click(timeout=timeout());return state()
    if kind=='submit':
        if policy.get('render_mode')=='render_existing_search_result':raise RuntimeError('interaction_blocked')
        field=page.locator('input,textarea,[role="searchbox"]').nth(cmd['ui']['index'])
        if not field.is_visible() or not field.is_enabled():raise RuntimeError('interaction_blocked')
        descriptors=page.evaluate(PROJECTION_SCRIPT,policy).get('inputs',[])
        matching=[x for x in descriptors if x.get('index')==cmd['ui']['index']]
        if len(descriptors)!=1 or len(matching)!=1 or matching[0].get('unsafe') or matching[0]!=cmd['ui']:raise RuntimeError('browser_search_ui_unsafe')
        field.fill(cmd['query'],timeout=timeout());guard()
        field.press('Enter',timeout=timeout());page.wait_for_timeout(min(1200,timeout()))
        return state()
    raise RuntimeError('interaction_blocked')

for line in sys.stdin:
    try:
        request=json.loads(line);result=command(request)
        print(json.dumps({'ok':True,'result':result}),flush=True)
        if request['command']=='close':break
    except Exception as exc:
        known={'challenge_detected','rate_limited','foreign_redirect','budget_exhausted','deadline_exhausted','interaction_blocked','browser_search_ui_unsafe','projection_budget_exhausted','network_budget_exhausted'}
        code=signal or (str(exc) if str(exc) in known else 'browser_javascript_error')
        print(json.dumps({'ok':False,'error':code,'counts':dict(counts)}),flush=True)
