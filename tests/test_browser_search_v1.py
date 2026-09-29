import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from dataclasses import replace
from product_tool.census.browser_contracts import BrowserBudget,detect_search_ui,browser_candidates,rendered_identity,VERSIONS,eligibility
from product_tool.census.browser_runtime import BrowserRuntime,BrowserFailure
from product_tool.census.browser_strategy import BrowserAssistedSearchStrategy
from product_tool.census.browser_snapshots import BrowserSnapshotStore,sanitize_browser_dom
from test_internal_search_v1 import identity,BASE
from product_tool.census.browser_projection import legacy_projection

RUNTIME=BrowserRuntime(True,'fake','fake1','fake-chromium1')
STATIC={'stop_reason':'unsafe_search_route','routes':[{'action_url':BASE,'query_parameter':'','rejection_reason':'query_parameter_not_declared'}]}
UI='<form role="search"><input type="search" name="q"></form>'
RESULT='<div class="product-card"><a href="/products/ABC-123">ABC-123</a></div><nav><a href="/products/XYZ-123">Nav product</a></nav><footer><a href="/support/ABC-123">ABC-123</a></footer>'
PRODUCT='<script type="application/ld+json">{"@type":"Product","model":"ABC-123","color":"black"}</script>'

class FakeBrowser:
    def __init__(self,pages=None):
        self.pages=pages or {'homepage':UI,'search':RESULT,'product':PRODUCT};self.calls=[];self.closed=False;self.counts={'contexts':0,'navigations':0,'network_requests':0};self.current=None
    def start(self):self.counts['contexts']+=1;self.calls.append('start')
    def call(self,command,**args):
        self.calls.append(command)
        if command=='state':return copy.deepcopy(self.current)
        phase='search' if command=='submit' else 'homepage' if args.get('url')==BASE else 'product'
        value=self.pages[phase]
        if isinstance(value,Exception):raise value
        self.counts['navigations']+=1;self.counts['network_requests']+=1
        self.current={'url':BASE+'search?q=ABC-123' if phase=='search' else args['url'],'html':value,'counts':dict(self.counts)}
        self.current['projection']=legacy_projection(value,self.current['url'],('example.com',))
        self.current.pop('html',None)
        return copy.deepcopy(self.current)
    def close(self):self.closed=True

def run(browser=None,**kwargs):
    runtime=kwargs.pop('runtime',RUNTIME);budget=kwargs.pop('budget',BrowserBudget())
    strategy=BrowserAssistedSearchStrategy(runtime=runtime,budget=budget,browser_factory=lambda *args:browser)
    return strategy.run(source_family='demo',source_url=BASE,allowed_hosts=('example.com',),expected=kwargs.pop('expected',identity()),static_result=kwargs.pop('static_result',STATIC),official_source_verified=kwargs.pop('official_source_verified',True),browser_assisted=kwargs.pop('browser_assisted',True),**kwargs)

class GateTests(unittest.TestCase):
    def test_default_disabled(self):
        s=BrowserAssistedSearchStrategy(runtime=RUNTIME,browser_factory=lambda *x:self.fail('browser launched'))
        r=s.run(source_family='demo',source_url=BASE,allowed_hosts=('example.com',),expected=identity(),static_result=STATIC,official_source_verified=True)
        self.assertEqual(r.stop_reason,'browser_assisted_disabled')
    def test_explicit_opt_in_required(self):
        b=FakeBrowser();self.assertEqual(run(b,browser_assisted=False).stop_reason,'browser_assisted_disabled');self.assertFalse(b.calls)
    def test_prior_protection_foreign_or_login_disallows(self):
        for prior in [{'stop_reason':'blocked'},{'stop_reason':'rate_limited'},{'stop_reason':'search_route_not_found','probe_results':[{'http_status':403}]},{'stop_reason':'search_route_not_found','redirect_evidence':[{'allowed':False}]},{'stop_reason':'unsafe_search_route','routes':[{'rejection_reason':'csrf_or_session_requirement'}]}]:
            b=FakeBrowser();self.assertEqual(run(b,static_result=prior).stop_reason,'browser_strategy_not_eligible');self.assertFalse(b.calls)
    def test_unverified_source_disallows(self):self.assertEqual(run(FakeBrowser(),official_source_verified=False).stop_reason,'browser_strategy_not_eligible')
    def test_no_results_requires_js_evidence(self):
        self.assertFalse(eligibility({'stop_reason':'search_no_results'},True)[0]);self.assertTrue(eligibility({'stop_reason':'search_no_results','strategy_evidence':{'js_search_ui':True}},True)[0])
    def test_unavailable_runtime(self):self.assertEqual(run(runtime=BrowserRuntime(False)).stop_reason,'browser_runtime_unavailable')

class UITests(unittest.TestCase):
    def test_arbitrary_input_rejected(self):self.assertEqual(detect_search_ui('<input type=text>',BASE,('example.com',))[1],'browser_search_ui_not_found')
    def test_searchbox(self):self.assertEqual(detect_search_ui('<input role=searchbox>',BASE,('example.com',))[0]['discovery_method'],'role_searchbox')
    def test_login_ambiguity(self):self.assertEqual(detect_search_ui('<form role=search action=/login><input type=search><input type=password></form>',BASE,('example.com',))[1],'browser_search_ui_unsafe')
    def test_secret_selector_not_logged(self):
        ui,_=detect_search_ui('<label for="session-secret-123">Search</label><input id="session-secret-123">',BASE,('example.com',))
        self.assertNotIn('session-secret',json.dumps(ui))
    def test_candidate_filter(self):
        c=browser_candidates(RESULT,response_url=BASE+'search',expected=identity(),source_family='demo',allowed_hosts=('example.com',))
        self.assertEqual([x.url for x in c],[BASE+'products/ABC-123'])

class StrategyTests(unittest.TestCase):
    def test_exact_model_and_context_closed(self):
        b=FakeBrowser();r=run(b);self.assertEqual(r.stop_reason,'browser_exact_model_found');self.assertTrue(b.closed);self.assertFalse(r.strategy_evidence['production_ready']);self.assertEqual(r.strategy_evidence['browser_usage']['contexts'],1)
    def test_body_text_not_identity(self):
        r=run(FakeBrowser({'homepage':UI,'search':RESULT,'product':'<h1>ABC-123</h1>'}));self.assertEqual(r.stop_reason,'browser_identity_insufficient')
    def test_variant_conflict(self):
        from product_tool.identity import VariantAttributes
        e=replace(identity(),variant_attributes=VariantAttributes({'color':'white'}))
        self.assertEqual(run(FakeBrowser(),expected=e).stop_reason,'browser_identity_conflict')
    def test_challenge_no_retry_closed(self):
        b=FakeBrowser({'homepage':UI,'search':'<div>Verify you are human</div>','product':PRODUCT});r=run(b)
        self.assertEqual(r.stop_reason,'challenge_detected');self.assertTrue(b.closed);self.assertEqual(b.calls.count('submit'),1);self.assertNotIn('product',b.calls)
    def test_foreign_transition(self):
        class Foreign(FakeBrowser):
            def call(self,command,**args):
                s=super().call(command,**args)
                if command=='submit':s['url']='https://foreign.test/'
                return s
        b=Foreign();self.assertEqual(run(b).stop_reason,'foreign_redirect');self.assertTrue(b.closed)
    def test_navigation_limit(self):
        b=FakeBrowser();r=run(b,budget=BrowserBudget(max_navigations=1));self.assertEqual(r.stop_reason,'budget_exhausted');self.assertEqual(b.counts['navigations'],1);self.assertTrue(b.closed)
    def test_invalid_budgets(self):
        for kw in [{'max_queries':3},{'max_contexts':2},{'deadline_seconds':61},{'operation_timeout_seconds':float('nan')},{'max_product_validations':4}]:
            with self.assertRaises(ValueError):BrowserBudget(**kw)
    def test_second_query_only_when_no_candidates(self):
        b=FakeBrowser();run(b);self.assertEqual(b.calls.count('submit'),1)
    def test_microdata_identity(self):
        html='<div itemscope itemtype="https://schema.org/Product"><meta itemprop="model" content="ABC-123"></div>'
        self.assertEqual(rendered_identity(html,expected=identity(),source_url=BASE).level.value,'exact_model')
        self.assertEqual(rendered_identity(sanitize_browser_dom(html),expected=identity(),source_url=BASE).level.value,'exact_model')

class ReplayTests(unittest.TestCase):
    def test_compatible_resume(self):
        first=run(FakeBrowser());b=FakeBrowser();r=run(b,checkpoint=first.checkpoint)
        self.assertEqual(r.stop_reason,'checkpoint_complete');self.assertFalse(b.calls)
    def test_version_incompatibility(self):
        first=run(FakeBrowser());old=copy.deepcopy(first.checkpoint);old['strategy_version']='old';b=FakeBrowser()
        self.assertEqual(run(b,checkpoint=old).stop_reason,'checkpoint_incompatible');self.assertFalse(b.calls)
    def test_snapshot_reprocessing_no_browser(self):
        with tempfile.TemporaryDirectory() as d:
            store=BrowserSnapshotStore(Path(d)/'snapshots.sqlite3');first=run(FakeBrowser(),snapshot_writer=store.writer(identity(),'demo'))
            digest=hashlib.sha256(store.path.read_bytes()).hexdigest();old=copy.deepcopy(first.checkpoint);old['result_parser_version']='old';old['candidates']=[]
            b=FakeBrowser();r=run(b,checkpoint=old,reprocess=True,snapshot_loader=store.load)
            self.assertEqual(r.stop_reason,'browser_exact_model_found');self.assertFalse(b.calls);self.assertEqual(r.budget_used.http_requests,0);self.assertEqual(hashlib.sha256(store.path.read_bytes()).hexdigest(),digest)
            self.assertNotIn('<script',json.dumps(r.checkpoint))
    def test_snapshot_missing(self):self.assertEqual(run(FakeBrowser(),checkpoint=run(FakeBrowser()).checkpoint,reprocess=True).stop_reason,'snapshot_missing')
    def test_registry_unchanged(self):
        root=Path(__file__).resolve().parents[1];files=list((root/'product_tool/config').glob('*.json'));before=[p.read_bytes() for p in files];run(FakeBrowser());self.assertEqual(before,[p.read_bytes() for p in files])


class AdditionalSafetyTests(unittest.TestCase):
    def test_http_protection_closes_without_retry(self):
        class Denied(FakeBrowser):
            def call(self,command,**kwargs):
                state=super().call(command,**kwargs);state['http_status']=403;return state
        b=Denied();r=run(b);self.assertEqual(r.stop_reason,'challenge_detected');self.assertTrue(b.closed);self.assertEqual(b.calls.count('goto'),1)
    def test_deadline(self):
        b=FakeBrowser();ticks=iter([0,61]);s=BrowserAssistedSearchStrategy(runtime=RUNTIME,browser_factory=lambda *x:b,clock=lambda:next(ticks,61))
        r=s.run(source_family='demo',source_url=BASE,allowed_hosts=('example.com',),expected=identity(),static_result=STATIC,official_source_verified=True,browser_assisted=True)
        self.assertEqual(r.stop_reason,'deadline_exhausted');self.assertTrue(b.closed)
    def test_dom_bound(self):
        b=FakeBrowser();r=run(b,budget=BrowserBudget(max_projection_bytes=100));self.assertEqual(r.stop_reason,'projection_budget_exhausted');self.assertTrue(b.closed)
    def test_cookie_banner_no_arbitrary_consent(self):
        class Cookie(FakeBrowser):
            def call(self,command,**kwargs):
                if command=='dismiss_cookies':raise BrowserFailure('interaction_blocked')
                state=super().call(command,**kwargs);state['cookie_banner']=True;return state
        b=Cookie();self.assertEqual(run(b).stop_reason,'interaction_blocked');self.assertTrue(b.closed)
    def test_hash_tamper(self):
        with tempfile.TemporaryDirectory() as d:
            store=BrowserSnapshotStore(Path(d)/'snapshots.sqlite3');cp=run(FakeBrowser(),snapshot_writer=store.writer(identity(),'demo')).checkpoint
            cp=copy.deepcopy(cp);cp['snapshots'][0]['content_sha256']='wrong';b=FakeBrowser()
            self.assertEqual(run(b,checkpoint=cp,reprocess=True,snapshot_loader=store.load).stop_reason,'snapshot_missing');self.assertFalse(b.calls)
    def test_no_placeholder_only_input(self):
        self.assertEqual(detect_search_ui('<input placeholder="Search">',BASE,('example.com',))[1],'browser_search_ui_not_found')
    def test_clean_snapshot(self):
        html='<form role=search><input role=searchbox id=session_123 aria-label=Search name=q><input name=csrf value=secret></form><script>cookie="secret"</script>'
        clean=sanitize_browser_dom(html);self.assertNotIn('session_123',clean);self.assertNotIn('secret',clean);self.assertIn('searchbox',clean)

if __name__=='__main__':unittest.main()
