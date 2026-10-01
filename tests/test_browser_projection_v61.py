import copy
import json
import unittest
from product_tool.census.browser_contracts import BrowserBudget,eligibility,completed_search_request
from product_tool.census.browser_projection import legacy_projection,projection_html
from product_tool.census.browser_resources import admit_resource
from product_tool.census.browser_strategy import BrowserAssistedSearchStrategy
from test_browser_search_v1 import FakeBrowser,RUNTIME,RESULT,PRODUCT,UI,run
from test_internal_search_v1 import BASE,identity

URL=BASE+'search?q=ABC-123'
STATIC_GET={'stop_reason':'search_no_results','routes':[{'action_url':BASE+'search','method':'GET','query_parameter':'q','constant_parameters':[],'disposition':'safe_get','source':'configured_endpoint'}],'completed_queries':[{'query':'ABC-123','request_url':URL,'final_url':URL,'access_status':'direct_access','outcome':'search_no_results'}],'probe_results':[{'url':URL,'http_status':200,'access_status':'direct_access','protection_status':'ordinary_page'}]}

class ExistingBrowser(FakeBrowser):
    def call(self,command,**args):
        if command=='submit':raise AssertionError('existing search must never submit')
        if command=='goto' and args['url']==URL:
            self.calls.append(('goto',args['url']));self.counts['navigations']+=1;self.counts['network_requests']+=1
            self.current={'url':URL,'projection':legacy_projection(RESULT,URL,('example.com',)),'counts':dict(self.counts)}
            return copy.deepcopy(self.current)
        return super().call(command,**args)

class ExistingTests(unittest.TestCase):
    def test_completed_get_eligible_without_js_flag(self):
        self.assertTrue(eligibility(STATIC_GET,True,expected=identity(),allowed_hosts=('example.com',),render_mode='render_existing_search_result')[0])
    def test_exact_saved_url_and_no_resubmit(self):
        b=ExistingBrowser();r=run(b,static_result=STATIC_GET,render_mode='render_existing_search_result')
        self.assertEqual(r.stop_reason,'browser_exact_model_found');self.assertEqual(b.calls[1],('goto',URL));self.assertNotIn('submit',b.calls)
        self.assertEqual(r.strategy_evidence['browser_usage']['queries'],0);self.assertIn('render_existing_search_started',r.checkpoint['events'])
    def test_incomplete_unsafe_foreign_and_query_mismatch(self):
        mutations=[('completed_queries',0,'query','OTHER'),('completed_queries',0,'request_url',URL+'&extra=1'),('completed_queries',0,'request_url',BASE+'different?q=ABC-123'),('completed_queries',0,'final_url','https://evil.test/search'),('routes',0,'method','POST'),('routes',0,'disposition','unsafe'),('probe_results',0,'http_status',403),('probe_results',0,'http_status',429),('probe_results',0,'protection_status','challenge_confirmed')]
        for section,index,key,value in mutations:
            cp=copy.deepcopy(STATIC_GET);cp[section][index][key]=value;b=ExistingBrowser()
            r=run(b,static_result=cp,render_mode='render_existing_search_result');self.assertEqual(r.stop_reason,'browser_strategy_not_eligible');self.assertFalse(b.calls)
    def test_missing_response_not_invented(self):
        cp=copy.deepcopy(STATIC_GET);cp['probe_results']=[]
        self.assertIsNone(completed_search_request(cp,identity(),('example.com',)))
    def test_unknown_mode_denied(self):self.assertEqual(run(FakeBrowser(),render_mode='new_strategy').stop_reason,'browser_strategy_not_eligible')
    def test_unverified_interactive_page_denied(self):self.assertEqual(run(FakeBrowser(),static_result={'stop_reason':'search_route_not_found'}).stop_reason,'browser_strategy_not_eligible')
    def test_empty_projection_specific_outcome(self):
        self.assertEqual(run(FakeBrowser({'homepage':UI,'search':'<body>nothing</body>'})).stop_reason,'search_projection_empty')
    def test_large_body_small_projection(self):
        self.assertEqual(run(FakeBrowser({'homepage':UI+'x'*1000000,'search':RESULT,'product':PRODUCT})).stop_reason,'browser_exact_model_found')
    def test_projection_version_invalidates(self):
        cp=run(FakeBrowser()).checkpoint;cp['projection_version']='0';b=FakeBrowser()
        self.assertEqual(run(b,checkpoint=cp).stop_reason,'checkpoint_incompatible');self.assertFalse(b.calls)
    def test_fragment_overflow(self):
        self.assertEqual(run(FakeBrowser(),budget=BrowserBudget(max_fragment_bytes=10)).stop_reason,'projection_budget_exhausted')

class ResourceTests(unittest.TestCase):
    def test_block_assets_and_downloads(self):
        counts={}
        for kind in ['image','font','media']:self.assertEqual(admit_resource(counts,kind,'/a',200),'blocked')
        self.assertEqual(admit_resource(counts,'document','/manual.pdf',200),'blocked');self.assertEqual(counts.get('network_requests',0),0)
    def test_cap_before_forwarding_and_categories(self):
        counts={}
        for kind in ['document','script','xhr','fetch','stylesheet']:self.assertEqual(admit_resource(counts,kind,'/search',5),'allowed')
        for _ in range(20):self.assertEqual(admit_resource(counts,'script','/a.js',5),'network_budget_exhausted')
        self.assertEqual(counts['network_requests'],5);self.assertEqual(counts['script_xhr_fetch_requests'],3);self.assertEqual(counts['stylesheet_requests'],1)
    def test_cap_validation(self):
        for key in ['max_network_requests','max_projection_bytes','max_fragment_bytes']:
            with self.assertRaises(ValueError):BrowserBudget(**{key:1000001})


class WorkerRoutingTests(unittest.TestCase):
    def worker(self):
        import io,runpy,sys,types
        from pathlib import Path
        from unittest.mock import patch
        fake=types.ModuleType('playwright.sync_api');fake.sync_playwright=lambda:None
        with patch.dict(sys.modules,{'playwright':types.ModuleType('playwright'),'playwright.sync_api':fake}),patch.object(sys,'stdin',io.StringIO('')),patch.object(sys,'path',[str(Path('product_tool/census').resolve())]+sys.path):
            module=runpy.run_path('product_tool/census/browser_worker.py')
        env=module['routed'].__globals__;env.update(policy={'allowed_hosts':['example.com'],'max_network_requests':2,'max_navigations':6},deadline=10**20,page=types.SimpleNamespace(main_frame=object()))
        return env
    def route(self,env,kind='script',url='https://example.com/a.js'):
        from types import SimpleNamespace
        calls=[]
        request=SimpleNamespace(url=url,resource_type=kind,method='GET',frame=env['page'].main_frame,is_navigation_request=lambda:kind=='document')
        route=SimpleNamespace(request=request,abort=lambda:calls.append('abort'),continue_=lambda:calls.append('continue'))
        env['routed'](route)
        return calls
    def test_worker_never_forwards_past_cap(self):
        env=self.worker()
        self.assertEqual(self.route(env),['continue']);self.assertEqual(self.route(env,'xhr'),['continue'])
        self.assertEqual(self.route(env,'fetch'),['abort']);self.assertEqual(env['signal'],'network_budget_exhausted')
        self.assertEqual(self.route(env),['abort']);self.assertEqual(env['counts']['network_requests'],2)
    def test_completed_search_drops_surplus_subresources_but_not_document(self):
        env=self.worker()
        env['policy']['render_mode']='render_existing_search_result'
        self.assertEqual(self.route(env),['continue'])
        self.assertEqual(self.route(env,'xhr'),['continue'])
        self.assertEqual(self.route(env,'stylesheet'),['abort'])
        self.assertEqual(env['counts']['network_requests'],2)
        self.assertEqual(env['counts']['capped_requests'],1)
        self.assertEqual(env['signal'],'')
        self.assertEqual(self.route(env,'document',url='https://example.com/next'),['abort'])
        self.assertEqual(env['signal'],'network_budget_exhausted')

    def test_worker_blocks_media_and_stops_403_without_retry(self):
        from types import SimpleNamespace
        env=self.worker()
        for kind in ['image','font','media']:self.assertEqual(self.route(env,kind),['abort'])
        self.assertEqual(env['counts']['network_requests'],0)
        env['response_event'](SimpleNamespace(url='https://example.com/search',status=403))
        self.assertEqual(self.route(env),['abort']);self.assertEqual(env['signal'],'challenge_detected')

class SnapshotBoundaryTests(unittest.TestCase):
    def test_only_schema_fields_survive(self):
        from product_tool.census.browser_projection import sanitize_projection
        p={'projection_version':'2','url':BASE,'cookies':'SECRET','html':'<body>SECRET</body>','inputs':[{'index':3,'id':'SESSIONSECRET','label':'Search','value':'SECRET'}],'fragments':[{'type':'json_ld','data':{'@type':'Product','model':'ABC-123','session':'SECRET'}}]}
        clean=json.dumps(sanitize_projection(p));self.assertNotIn('SECRET',clean);self.assertNotIn('index',clean);self.assertIn('ABC-123',clean)

if __name__=='__main__':unittest.main()
