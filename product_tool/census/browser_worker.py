"""Isolated Playwright worker. JSON lines protocol; opt-in guarded public session."""
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
public_session=None
public_stack_path=None
diagnostic_context={}
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
    if kind.startswith('public_'):return public_command(cmd)
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

def public_command(cmd):
    """Same guarded persistent public transport, reused in this worker."""
    global public_session
    import base64
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
    from product_tool.census.public_browser import PublicBrowserSession
    from product_tool.census.browser_contracts import BrowserBudget
    kind=cmd['command'];timings=[]
    if kind=='public_start':
        # The regular isolated search session is closed before opening the
        # explicitly requested public context: never two active contexts.
        if context:context.close()
        if browser:browser.close()
        if p:p.stop()
        options=dict(cmd['options']);timing_path=Path(options.pop('timing_path'))
        options['budget']=BrowserBudget(**options['budget'])
        public_session=PublicBrowserSession(**options);public_session.start()
        def event(name,**value):
            record={'event':'browser_event','phase':name,'timestamp':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),'session_id':public_session.session_id,**diagnostic_context,**value}
            with timing_path.open('a',encoding='utf8') as f:f.write(json.dumps(record)+'\n')
        public_session.page.on('domcontentloaded',lambda:event('dom_ready',url=public_session.page.url))
        public_session.page.on('load',lambda:event('load',url=public_session.page.url))
        public_session.page.on('response',lambda r:event('main_response',url=r.url,status=r.status) if r.request.is_navigation_request() and r.request.frame==public_session.page.main_frame else None)
        public_session.page.on('requestfailed',lambda req:event('request_failed',url=req.url,error=req.failure) if req.is_navigation_request() else None)
        public_session.page.on('close',lambda:event('page_closed'))
    elif kind=='public_goto':public_session.call('goto',url=cmd['url'])
    elif kind=='public_snapshot':
        result=public_session.snapshot(after_manual=bool(cmd.get('after_manual')));result.update(total_navigations=public_session.total_navigations,dom_state='captured_after_domcontentloaded',signal=public_session.signal);return result
    elif kind=='public_revision':
        url=public_session.select_revision(cmd['pnc']);return {'url':url,'total_navigations':public_session.total_navigations}
    elif kind=='public_binary':
        response=public_session.binary_transport(cmd['max_bytes']).get(cmd['url'],timeout=cmd['timeout'],allow_redirects=cmd['allow_redirects'])
        return {'url':response.url,'status_code':response.status_code,'headers':dict(response.headers),'body':base64.b64encode(response.content).decode(),'history':[{'url':x.url,'status_code':x.status_code,'headers':dict(x.headers)} for x in response.history]}
    elif kind=='public_close':public_session.close();return {'closed':True}
    else:raise RuntimeError('interaction_blocked')
    return {'url':public_session.page.url,'status_code':public_session.status,'total_navigations':public_session.total_navigations,'session_id':public_session.session_id,'signal':public_session.signal,'cookie_count':len(public_session.context.cookies()),'timing_events':list(public_session.events),'dom_state':'domcontentloaded' if public_session.status==200 else 'unknown'}

for line in sys.stdin:
    stack_file=None
    try:
        request=json.loads(line)
        if request.get('command','').startswith('public_'):
            import faulthandler
            if request['command']=='public_start':public_stack_path=Path(request['options']['timing_path']).with_suffix('.stack.log')
            diagnostic_context.clear();diagnostic_context.update(request.get('diagnostic_context',{}))
            if public_stack_path:
                stack_file=public_stack_path.open('a',encoding='utf8')
                stack_file.write(json.dumps({'stage':request['command'],'url':request.get('url',''),'job':diagnostic_context})+'\n');stack_file.flush()
                faulthandler.dump_traceback_later(max(.01,float(request.get('diagnostic_wall_timeout',10))-.2),file=stack_file)
        result=command(request)
        print(json.dumps({'ok':True,'result':result}),flush=True)
        if request['command'] in {'close','public_close'}:break
    except Exception as exc:
        if request.get('command','').startswith('public_'):
            detail=dict(public_session.counts) if public_session else {}
            detail.update(document_status=public_session.status if public_session else None,signal=public_session.signal if public_session else '')
            print(json.dumps({'ok':False,'error':str(exc),'counts':detail}),flush=True)
            continue
        known={'challenge_detected','rate_limited','foreign_redirect','budget_exhausted','deadline_exhausted','interaction_blocked','browser_search_ui_unsafe','projection_budget_exhausted','network_budget_exhausted'}
        code=signal or (str(exc) if str(exc) in known else 'browser_javascript_error')
        print(json.dumps({'ok':False,'error':code,'counts':dict(counts)}),flush=True)
    finally:
        if stack_file:
            faulthandler.cancel_dump_traceback_later();stack_file.close()
