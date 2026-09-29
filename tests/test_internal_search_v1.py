import hashlib
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import unittest

from product_tool.census.discovery import detect_internal_search, validate_structured_product_identity
from product_tool.census.endpoint_probe import AccessProbe, ProbePolicy
from product_tool.census.internal_search_strategy import InternalSearchStrategy, generate_search_queries, parse_search_results, internal_search_readiness
from product_tool.census.sitemap_strategy import DiscoveryBudget
from product_tool.identity import ProductIdentity, VariantAttributes
from test_sitemap_discovery_v1 import FakeProbe, expected_identity

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / 'tests/fixtures/stage5'
BASE = 'https://example.com/'
CONFIG = ({'url': BASE+'search', 'query_parameter': 'q'},)


def fixture(name):
    return (FIX/name).read_text(encoding='utf-8-sig')


def identity():
    return expected_identity(variants=False)


def run(probe, **kwargs):
    budget = kwargs.pop('budget', DiscoveryBudget(max_http_requests=10, max_product_candidates=20, min_interval_seconds=0))
    return InternalSearchStrategy(probe=probe, budget=budget).run(source_family='demo', source_url=BASE, allowed_hosts=('example.com',), expected=kwargs.pop('expected', identity()), configured_endpoints=kwargs.pop('configured_endpoints', CONFIG), **kwargs)


def pages(product=None):
    return {BASE+'search?q=ABC-123': '<a href="/products/ABC-123">ABC-123</a>', BASE+'search?q=ABC123': '<a href="/products/ABC-123">ABC-123</a>', BASE+'products/ABC-123': product or fixture('product.html')}


class RouteTests(unittest.TestCase):
    def route(self, html):
        return detect_internal_search(html, BASE)[0]

    def test_get_query_and_constants(self):
        r = self.route(fixture('search_form.html'))
        self.assertTrue(r.executable)
        self.assertEqual(r.query_url('ABC/01'), BASE+'search?lang=en&keyword=ABC%2F01')
        self.assertEqual(r.source, 'html_search_form')

    def test_post_detected_never_executed(self):
        probe = FakeProbe({BASE: '<form method=post action=/search><input name=q></form>'})
        result = run(probe, configured_endpoints=())
        self.assertEqual(result.stop_reason, 'unsafe_search_route')
        self.assertEqual(probe.calls, [BASE])
        self.assertEqual(result.strategy_evidence['routes'][0]['method'], 'POST')

    def test_foreign_action(self):
        self.assertFalse(self.route('<form action="https://foreign.test/search"><input name=q></form>').executable)

    def test_login_forms_rejected(self):
        for attrs, inputs in [('action=/account', '<input name=q>'), ('id=login action=/search', '<input name=q>'), ('action=/search', '<input type=password><input name=q>'), ('action=/search', '<input type=file><input name=q>')]:
            self.assertFalse(self.route(f'<form {attrs}>{inputs}</form>').executable)

    def test_tokens_redacted(self):
        r = self.route('<form action="/search?session=SECRET"><input name=q><input type=hidden name=csrf value=SECRET></form>')
        self.assertFalse(r.executable)
        self.assertNotIn('SECRET', json.dumps(r.to_dict()))

    def test_javascript_api_rejected(self):
        for attrs in ['action=/api/search', 'action=/graphql', 'action=/search onsubmit="foo()"']:
            self.assertFalse(self.route(f'<form {attrs}><input name=q></form>').executable)

    def test_script_routes_not_discovered(self):
        self.assertEqual(detect_internal_search('<script>"<a href=\"/search?q=x\">"</script>', BASE), ())

    def test_link_evidence(self):
        r = self.route('<a href="/search?q=abc">Search</a>')
        self.assertTrue(r.executable)
        self.assertEqual(r.source, 'first_party_search_link')

    def test_configured_api_allowed(self):
        r = detect_internal_search('', BASE, configured_endpoints=({'url': '/api/search', 'query_parameter':'q'},))[0]
        self.assertTrue(r.executable)


class QueryTests(unittest.TestCase):
    def test_priority_and_bound(self):
        e = replace(identity(), seller_sku='SKU-123', model_candidates=('MODEL-456', 'UNUSED-999'))
        q = generate_search_queries(e)
        self.assertEqual([x['query'] for x in q], ['SKU-123','MODEL-456','SKU123'])
        self.assertTrue(all(x['reason'] for x in q))

    def test_preserve_significant_punctuation(self):
        e = replace(identity(), seller_sku='ABC-123.4/01', model_candidates=())
        self.assertEqual([x['query'] for x in generate_search_queries(e)], ['ABC-123.4/01','ABC123.4/01'])

    def test_bosch_index_bounded(self):
        e = replace(identity(), brand_canonical='bosch', seller_sku='WGG-123/01', model_candidates=())
        self.assertEqual([x['query'] for x in generate_search_queries(e)], ['WGG-123/01','WGG123/01','WGG-123'])

    def test_no_user_data_or_wb_sku(self):
        for code in ['12345678', 'AB', 'black', '256 GB', 'user@example.com', 'John Doe']:
            e = replace(identity(), seller_sku=code, model_candidates=(), title_raw='personal title ABC-123', wb_sku='12345678')
            self.assertEqual(generate_search_queries(e), ())


class StrategyTests(unittest.TestCase):
    def test_dedup_tracking_and_itemlist(self):
        c = parse_search_results(fixture('results.html'), response_url=BASE+'search', expected=identity(), source_family='demo', allowed_hosts=('example.com',))
        self.assertEqual(len(c),2)
        self.assertEqual(c[0].url,BASE+'products/ABC-123')
        self.assertFalse(c[0].identity_verification)
        self.assertTrue(any('html_product_card' in x for x in c[0].ranking_reasons))

    def test_title_url_and_body_never_prove_identity(self):
        r = run(FakeProbe(pages('<h1>ABC-123</h1> body ABC-123')))
        self.assertEqual(r.stop_reason,'results_identity_insufficient')
        self.assertEqual(r.candidates[0].identity_verification['level'],'insufficient')

    def test_exact_structured_model(self):
        r = run(FakeProbe(pages()))
        self.assertEqual(r.stop_reason,'exact_model_found')
        self.assertEqual(r.strategy,'internal_search')
        self.assertFalse(internal_search_readiness(r)['production_ready'])

    def test_variant_conflict_and_missing(self):
        e = replace(identity(),variant_attributes=VariantAttributes({'color':'white'}))
        self.assertEqual(run(FakeProbe(pages()),expected=e).stop_reason,'structured_identity_conflict')
        e = replace(identity(),variant_attributes=VariantAttributes({'color':'black','hardware_revision':'V2'}))
        self.assertEqual(run(FakeProbe(pages()),expected=e).candidates[0].identity_verification['level'],'exact_model')

    def test_exact_variant(self):
        e = replace(identity(),variant_attributes=VariantAttributes({'color':'black'}))
        self.assertEqual(run(FakeProbe(pages()),expected=e).stop_reason,'exact_variant_found')

    def test_service_index_from_model_when_sku_absent(self):
        e = replace(identity(),seller_sku='WGG123/01',model_candidates=('WGG123/01',),variant_attributes=VariantAttributes({'service_index':'01'}))
        r = validate_structured_product_identity('<script type="application/ld+json">{"@type":"Product","model":"WGG123/01"}</script>',expected=e)
        self.assertEqual(r.level.value,'exact_variant')

    def test_403_429_stop_and_resume(self):
        for status, stop in [(403,'blocked'),(429,'rate_limited')]:
            p=FakeProbe({BASE+'search?q=ABC-123':(status,'')})
            r=run(p)
            self.assertEqual(r.stop_reason,stop)
            self.assertEqual(len(p.calls),1)
            self.assertEqual(run(p,checkpoint=r.checkpoint).stop_reason,'checkpoint_complete')
            self.assertEqual(len(p.calls),1)

    def test_completed_resume_and_refresh(self):
        p=FakeProbe(pages());r=run(p);count=len(p.calls)
        cp=json.loads(json.dumps(r.checkpoint))
        self.assertEqual(run(p,checkpoint=cp).stop_reason,'checkpoint_complete')
        self.assertEqual(len(p.calls),count)
        run(p,checkpoint=cp,refresh=True)
        self.assertEqual(len(p.calls),count*2)

    def test_partial_resume_skips_successful_query(self):
        snapshots=[];p=FakeProbe(pages())
        run(p,checkpoint_callback=lambda cp:snapshots.append(json.loads(json.dumps(cp))))
        cp=next(x for x in snapshots if len(x['completed_queries'])==1)
        p2=FakeProbe(pages());run(p2,checkpoint=cp)
        self.assertNotIn(BASE+'search?q=ABC-123',p2.calls)

    def test_checkpoint_binding(self):
        r=run(FakeProbe(pages()))
        with self.assertRaises(ValueError):
            run(FakeProbe({}),checkpoint=r.checkpoint,expected=replace(identity(),seller_sku='OTHER123'))

    def test_request_budget(self):
        p=FakeProbe(pages());r=run(p,budget=DiscoveryBudget(max_http_requests=1,min_interval_seconds=0))
        self.assertEqual(len(p.calls),1)
        self.assertEqual(r.budget_used.http_requests,1)
        self.assertEqual(r.stop_reason,'budget_exhausted')

    def test_page_and_candidate_caps(self):
        data=pages();links=''.join(f'<a href="/products/ABC-123-{i}">ABC-123</a>' for i in range(50))
        data[BASE+'search?q=ABC-123']=links;data[BASE+'search?q=ABC123']=links
        for i in range(50): data[BASE+f'products/ABC-123-{i}']='body'
        r=run(FakeProbe(data),budget=DiscoveryBudget(max_http_requests=100,max_product_candidates=100,max_product_pages=100,min_interval_seconds=0))
        self.assertEqual(len(r.candidates),20)
        self.assertEqual(r.budget_used.product_pages,3)
        self.assertLessEqual(r.budget_used.http_requests,10)

    def test_registry_unchanged(self):
        files=list((ROOT/'product_tool/config').glob('*.json'))
        before={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
        run(FakeProbe(pages()))
        self.assertEqual(before,{p:hashlib.sha256(p.read_bytes()).hexdigest() for p in files})


class Response:
    def __init__(self,url,status=200,location=None,body=''):
        self.url=url;self.status_code=status;self.headers={'content-type':'text/html'}
        if location:self.headers['Location']=location
        self.history=[];self.encoding='utf-8';self.cookies=SimpleNamespace(get_dict=lambda:{})
        self.body=body;self.closed=False
    def iter_content(self,chunk_size): yield self.body.encode()
    def close(self):self.closed=True


class Session:
    def __init__(self,responses):self.responses=responses;self.calls=[]
    def get(self,url,**kwargs):
        self.calls.append((url,kwargs));return self.responses[url]


class TransportTests(unittest.TestCase):
    def test_foreign_redirect_never_requested(self):
        url=BASE+'search?q=ABC-123';s=Session({url:Response(url,302,'https://foreign.test/')})
        r=run(AccessProbe(s,policy=ProbePolicy(min_interval_seconds=0)))
        self.assertEqual(len(s.calls),1)
        self.assertFalse(s.calls[0][1]['allow_redirects'])
        self.assertEqual(r.stop_reason,'unsafe_search_route')

    def test_redirects_count_towards_budget(self):
        url=BASE+'search?q=ABC-123';s=Session({url:Response(url,302,BASE+'next'),BASE+'next':Response(BASE+'next',302,url)})
        r=run(AccessProbe(s,policy=ProbePolicy(min_interval_seconds=0)),budget=DiscoveryBudget(max_http_requests=2,min_interval_seconds=0))
        self.assertEqual(len(s.calls),2)
        self.assertEqual(r.budget_used.http_requests,2)
        self.assertEqual(r.stop_reason,'budget_exhausted')

    def test_deadline_before_request(self):
        tick=iter([0,2]);p=FakeProbe({})
        strategy=InternalSearchStrategy(probe=p,budget=DiscoveryBudget(deadline_seconds=1),clock=lambda:next(tick, 2))
        r=strategy.run(source_family='demo',source_url=BASE,allowed_hosts=('example.com',),expected=identity(),configured_endpoints=CONFIG)
        self.assertEqual(r.stop_reason,'deadline_exhausted');self.assertFalse(p.calls)

    def test_confirmed_challenge_stops(self):
        url=BASE+'search?q=ABC-123';s=Session({url:Response(url,body='<form id="challenge-form">Verify you are human</form>')})
        r=run(AccessProbe(s,policy=ProbePolicy(min_interval_seconds=0)))
        self.assertEqual(r.stop_reason,'blocked');self.assertEqual(len(s.calls),1)

    def test_regional_redirect_evidence(self):
        url=BASE+'search?q=ABC-123';end='https://uk.example.com/search?q=ABC-123'
        s=Session({url:Response(url,302,end),end:Response(end),BASE+'search?q=ABC123':Response(BASE+'search?q=ABC123')})
        r=run(AccessProbe(s,policy=ProbePolicy(min_interval_seconds=0)))
        self.assertEqual(r.budget_used.http_requests,3)
        self.assertEqual(r.redirect_evidence[0]['final_url'],end)



class HardeningTests(unittest.TestCase):
    def test_navigation_support_and_blog_are_not_products(self):
        html='<nav class="product-navigation"><a href="/">Home</a><a href="/blogs/news">News</a><a href="/support/product-support/manuals-software">Manuals</a></nav><article class="product-card"><a href="/products/ABC-123?_sid=secret&_pos=1&_ss=r&utm_campaign=test">ABC-123</a></article>'
        found=parse_search_results(html,response_url=BASE+'search',expected=identity(),source_family='demo',allowed_hosts=('example.com',))
        self.assertEqual([x.url for x in found],[BASE+'products/ABC-123'])
        self.assertNotIn('secret',json.dumps([x.to_dict() for x in found]))

    def test_personal_constants_are_not_retained(self):
        route=detect_internal_search('<form action="/search?email=private@example.com"><input name=q></form>',BASE)[0]
        self.assertFalse(route.executable)
        self.assertNotIn('private@example.com',json.dumps(route.to_dict()))

    def test_submit_override_is_not_executed(self):
        route=detect_internal_search('<form action=/search><input name=q><button formmethod=post>Go</button></form>',BASE)[0]
        self.assertFalse(route.executable)

    def test_percent_encoded_account_route(self):
        route=detect_internal_search('<form action=/%61ccount><input name=q></form>',BASE)[0]
        self.assertFalse(route.executable)

    def test_invalid_budget_values(self):
        for args in [{'deadline_seconds':float('nan')},{'max_http_requests':float('inf')},{'max_product_pages':1.5},{'min_interval_seconds':float('nan')}]:
            with self.assertRaises(ValueError):DiscoveryBudget(**args)

    def test_pending_checkpoint_with_blocking_query_stops(self):
        p=FakeProbe({BASE+'search?q=ABC-123':(403,'')});r=run(p)
        cp=dict(r.checkpoint);cp['status']='pending';cp['stop_reason']=''
        resumed=run(p,checkpoint=cp)
        self.assertEqual(resumed.stop_reason,'checkpoint_complete');self.assertEqual(len(p.calls),1)

    def test_response_stream_failure_is_reported(self):
        import requests
        class Broken(Response):
            def iter_content(self,chunk_size):raise requests.ConnectionError('do not persist sensitive exception')
        u=BASE+'search?q=ABC-123';u2=BASE+'search?q=ABC123'
        response=Broken(u);s=Session({u:response,u2:Response(u2)})
        r=run(AccessProbe(s,policy=ProbePolicy(min_interval_seconds=0)))
        self.assertEqual(r.stop_reason,'search_no_results');self.assertTrue(response.closed)
        self.assertEqual(r.checkpoint['probe_results'][0]['error'],'Response stream failed')

    def test_javascript_only_homepage_outcome(self):
        s=Session({BASE:Response(BASE,body='<noscript>JavaScript is required</noscript>')})
        r=run(AccessProbe(s,policy=ProbePolicy(min_interval_seconds=0)),configured_endpoints=())
        self.assertEqual(r.stop_reason,'search_javascript_required');self.assertEqual(len(s.calls),1)

    def test_malformed_product_type_is_insufficient(self):
        result=validate_structured_product_identity('<script type="application/ld+json">{"@type":{"unexpected":true}}</script>',expected=identity())
        self.assertEqual(result.level.value,'insufficient')

    def test_dry_run_scope_and_configured_lg_route(self):
        from product_tool.census.runner_v5 import source_specs, configured_routes
        sources=source_specs()
        self.assertEqual(len(sources),6)
        lg=next(x for x in sources if x.source_family=='lg_kz')
        self.assertEqual(configured_routes(lg)[0]['query_parameter'],'q')
        self.assertIn('/kz/search?',configured_routes(lg)[0]['url'])

class FinalSafetyTests(unittest.TestCase):
    def test_redirected_protected_host_stays_stopped(self):
        url=BASE+'search?q=ABC-123';end='https://uk.example.com/search?q=ABC-123'
        session=Session({url:Response(url,302,end),end:Response(end,403)})
        probe=AccessProbe(session,policy=ProbePolicy(min_interval_seconds=0))
        result=run(probe)
        self.assertEqual(result.stop_reason,'blocked')
        probe.probe('https://uk.example.com/another',allowed_hosts=('example.com',))
        self.assertEqual(len(session.calls),2)

    def test_resumed_deadline_is_cumulative(self):
        p=FakeProbe(pages());r=run(p)
        cp=dict(r.checkpoint);cp['status']='pending';cp['stop_reason']='';cp['elapsed_seconds']=100
        cp['completed_queries']=[];cp['budget_used']=dict(cp['budget_used']);cp['budget_used']['search_queries']=0
        p2=FakeProbe({});resumed=run(p2,checkpoint=cp)
        self.assertEqual(resumed.stop_reason,'deadline_exhausted');self.assertFalse(p2.calls)


if __name__=='__main__':unittest.main()
