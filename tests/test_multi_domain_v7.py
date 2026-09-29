import copy
import unittest
from dataclasses import replace
from unittest.mock import Mock
from product_tool.identity import ProductIdentity,VerificationLevel
from product_tool.census.official_domains import load_domains,routed_domains
from product_tool.census.multi_domain import MultiDomainDiscovery,MultiDomainBudget,best_official,dealer_gate
from product_tool.census.scoped_access import AccessLedger,AccessObservation
from product_tool.census.models import AccessStatus,ProtectionStatus

def identity(brand='LG',category=''):
    return ProductIdentity.from_product({'brand':brand,'category':category,'name':'ABC123','search_code':'ABC123','model_candidates':['ABC123']})
def result(domain,level=None):
    return {'domain_id':domain.domain_id,'outcome':'bounded_discovery_complete','http_requests':1,'search_evidence_available':True,'candidates':[] if not level else [{'url':domain.url+'product/ABC123','identity_verification':{'level':level,'evidence':[]}}]}

class DomainPolicyTests(unittest.TestCase):
    def setUp(self):self.domains=load_domains();self.lg=[x for x in self.domains if x.source_family=='lg']
    def test_registry_not_production_enabled(self):self.assertTrue(all(not d.enabled for d in self.domains));self.assertEqual(routed_domains(self.domains,identity(),'lg'),())
    def test_exact_regional_beats_global_family(self):
        regional,global_=self.lg[:2]
        self.assertEqual(best_official([result(regional,'exact_model'),result(global_,'family_only')],self.lg)['domain_id'],regional.domain_id)
    def test_exact_variant_beats_model(self):self.assertEqual(best_official([result(self.lg[0],'exact_variant'),result(self.lg[1],'exact_model')],self.lg)['domain_id'],self.lg[0].domain_id)
    def test_global_tie_only_after_completeness(self):
        a=result(self.lg[0],'exact_model');b=result(self.lg[1],'exact_model')
        self.assertEqual(best_official([a,b],self.lg)['domain_id'],self.lg[1].domain_id)
        a['candidates'][0]['identity_verification']['evidence']=[{'evidence_type':'model','normalized_value':'ABC123','state':'match'}]
        self.assertEqual(best_official([a,b],self.lg)['domain_id'],self.lg[0].domain_id)
    def test_domains_beyond_budget_do_not_enable_dealers(self):
        s=MultiDomainDiscovery(self.domains,lambda d,*args:result(d),budget=MultiDomainBudget(max_domains=1))
        r=s.run(identity(),'lg',research=True);self.assertEqual(r['outcome'],'official_search_incomplete');self.assertFalse(r['dealer_fallback']['allowed'])
    def test_all_domains_needed_for_not_found(self):
        seen=[]
        def execute(d,*args):seen.append(d.domain_id);return result(d)
        r=MultiDomainDiscovery(self.domains,execute).run(identity(),'lg',research=True)
        self.assertEqual(len(seen),4);self.assertEqual(r['outcome'],'official_exact_product_not_found');self.assertFalse(r['browser_used'])
    def test_complete_resume_no_executor(self):
        s=MultiDomainDiscovery(self.domains,lambda d,*args:result(d));first=s.run(identity(),'lg',research=True)
        s.executor=lambda *args:self.fail('network');self.assertEqual(s.run(identity(),'lg',research=True,checkpoint=first)['new_http_requests'],0)
        bad=copy.deepcopy(first);bad['scope']='wrong';self.assertEqual(s.run(identity(),'lg',research=True,checkpoint=bad)['outcome'],'checkpoint_incompatible')
    def test_no_evidence_is_unavailable_not_absent(self):
        r=MultiDomainDiscovery(self.domains,lambda d,*a:dict(result(d),search_evidence_available=False)).run(identity(),'lg',research=True)
        self.assertEqual(r['outcome'],'official_search_unavailable')
    def test_bosch_division_separation(self):
        tools=next(d for d in self.domains if d.source_family=='bosch_tools')
        from product_tool.census.catalog import CATEGORY_GROUP_RULES
        category=next(tokens[0] for group,tokens in CATEGORY_GROUP_RULES if group=='tools_garden')
        self.assertFalse(routed_domains(self.domains,identity('BOSCH',category),'bosch_home',research=True))
        self.assertTrue(routed_domains(self.domains,identity('BOSCH',category),'bosch_tools',research=True))

class ScopedAccessTests(unittest.TestCase):
    def test_browser_block_does_not_pause_http_or_regions(self):
        prior=AccessObservation('www.lg.com','https://www.lg.com/kz/search?q=ABC123','browser','render_existing_search_result','captcha_or_blocked','challenge_detected',None,'old')
        ledger=AccessLedger([prior]);self.assertFalse(ledger.paused(prior.endpoint));self.assertFalse(ledger.paused('https://www.lge.co.kr/'))
    def test_http_pause_exact_host_only(self):
        response=Mock(final_url='https://www.lg.com/kz/search',url='https://www.lg.com/kz/search',access_status=AccessStatus.CAPTCHA_OR_BLOCKED,protection_status=ProtectionStatus.CHALLENGE_CONFIRMED,http_status=403,checked_at='now')
        l=AccessLedger();l.record(response);self.assertTrue(l.paused('https://www.lg.com/robots.txt'));self.assertFalse(l.paused('https://www.lge.co.kr/'));self.assertFalse(l.paused('https://www.lg.com/kz/search','browser'))

class DealerTests(unittest.TestCase):
    def test_exact_existing_allowlist_only(self):
        from product_tool.sources import default_source_registry
        source=default_source_registry().get('sulpak');official={'outcome':'official_exact_product_not_found','all_official_domains_considered':True}
        for category in source.category_allowlist:self.assertTrue(dealer_gate(identity(category=category),official)['allowed'])
        for brand,category in [('Samsung',source.category_allowlist[0]),('LG','TV'),('LG','monitor'),('LG','split system')]:self.assertFalse(dealer_gate(identity(brand,category),official)['allowed'])
    def test_early_dealer_gate_denied(self):self.assertFalse(dealer_gate(identity(),{'outcome':'official_search_incomplete'})['allowed'])
    def test_no_browser_import_in_stage7(self):
        import ast
        from pathlib import Path
        for name in ['multi_domain','http_domain_discovery','official_domains','scoped_access']:
            tree=ast.parse(Path('product_tool/census/'+name+'.py').read_text(encoding='utf-8-sig'))
            for node in ast.walk(tree):
                if isinstance(node,ast.ImportFrom):self.assertNotIn('browser',node.module or '')
                if isinstance(node,ast.Import):self.assertTrue(all(not any(s in n.name for s in ['playwright','selenium','browser']) for n in node.names))


class FieldProvenanceTests(unittest.TestCase):
    def test_dealer_cannot_overwrite_official_or_cross_variant(self):
        from product_tool.policy import SourceValue
        from product_tool.sources import SourceRole,default_source_registry
        from product_tool.census.multi_source_fields import resolve_card_fields
        category=default_source_registry().get('sulpak').category_allowlist[0]
        e=identity(category=category);official={'outcome':'official_exact_product_not_found','all_official_domains_considered':True}
        def value(field,text,source,role,variant='v1'):
            return SourceValue(field,text,source,role,VerificationLevel.EXACT_MODEL,variant,{'source':source,'url':'https://example.com/product','fetched_at':'2026-09-22','identity_level':'exact_model','extraction_method':'structured','confidence':1})
        values=[value('width',60,'official',SourceRole.MANUFACTURER),value('width',61,'sulpak',SourceRole.RETAILER),value('weight',50,'sulpak',SourceRole.RETAILER),value('height',90,'sulpak',SourceRole.RETAILER,'v2')]
        r=resolve_card_fields(values,expected=e,official_result=official,target_variant_key='v1')
        self.assertEqual({f['field_name']:f['value'] for f in r['fields']},{'width':60,'weight':50})
        self.assertTrue(any(x['reason']=='different_variant' for x in r['reviews']))
        self.assertTrue(any(x['reason']=='dealer_official_conflict_official_retained' for x in r['reviews']))
    def test_unapproved_dealer_and_missing_provenance_ignored(self):
        from product_tool.policy import SourceValue
        from product_tool.sources import SourceRole
        from product_tool.census.multi_source_fields import resolve_card_fields
        v=SourceValue('weight',2,'unknown',SourceRole.DEALER,VerificationLevel.EXACT_MODEL,'v',{})
        r=resolve_card_fields([v],expected=identity(),official_result={'outcome':'official_search_incomplete'},target_variant_key='v')
        self.assertFalse(r['fields'])

class HTTPExecutorTests(unittest.TestCase):
    def test_declared_query_sitemap_identity_and_no_guessed_product_url(self):
        from product_tool.census.endpoint_probe import AccessProbe
        from product_tool.census.http_domain_discovery import HTTPDomainDiscovery
        from product_tool.census.models import EndpointCapability
        from types import SimpleNamespace
        calls=[]
        pages={'https://example.com/':'<form action="/search"><input type="search" name="q"></form>','https://example.com/search?q=ABC123':'<div class="product-card"><a href="/products/ABC123">ABC123</a></div>','https://example.com/robots.txt':'Sitemap: https://example.com/map.xml','https://example.com/map.xml':'<urlset><url><loc>https://example.com/products/ABC123</loc></url></urlset>','https://example.com/products/ABC123':'<script type="application/ld+json">{"@type":"Product","model":"ABC123"}</script>'}
        class Probe:
            def probe(self,url,**kw):
                calls.append(url);kw['request_guard'](url)
                base=AccessProbe()._result(url,kw['capability'],kw['sample_type'],AccessStatus.DIRECT_ACCESS,200,(url,),url)
                return replace(base,diagnostic_text=pages.get(url,''))
        d=replace(load_domains()[0],domain_id='test',url='https://example.com/',page_hosts=('example.com',),support_hosts=(),capabilities={})
        r=HTTPDomainDiscovery(probe=Probe())(d,identity(),MultiDomainBudget(),10)
        self.assertEqual(r['candidates'][0]['identity_verification']['level'],'exact_model')
        self.assertTrue(all(url in pages for url in calls));self.assertLessEqual(r['http_requests'],10)
    def test_redirect_budget_is_charged_before_request(self):
        from product_tool.census.endpoint_probe import AccessProbe
        from product_tool.census.http_domain_discovery import HTTPDomainDiscovery
        class Probe:
            def probe(self,url,**kw):
                for _ in range(3):kw['request_guard'](url)
                raise AssertionError('past hard cap')
        d=load_domains()[0]
        r=HTTPDomainDiscovery(probe=Probe())(d,identity(),MultiDomainBudget(),2)
        self.assertEqual(r['http_requests'],2);self.assertEqual(r['outcome'],'domain_request_budget_exhausted')

class FinalScopeTests(unittest.TestCase):
    def test_partial_composite_query_does_not_claim_absence(self):
        e=ProductIdentity.from_product({'brand':'Samsung','category':'vacuum','name':'Jet_70_turbo/(VS15T7031R4/EV)','search_code':'Jet_70_turbo/(VS15T7031R4/EV)'})
        r=MultiDomainDiscovery(load_domains(),lambda d,*a:result(d)).run(e,'samsung',research=True)
        self.assertEqual(r['outcome'],'official_search_incomplete');self.assertFalse(r['identity_query_scope_complete'])
    def test_budget_rejects_nonfinite_or_fractional_counts(self):
        for kw in [{'max_domains':1.5},{'max_requests_per_domain':True},{'deadline_per_domain':float('nan')},{'max_queries':0}]:
            with self.assertRaises(ValueError):MultiDomainBudget(**kw)

class StructuredEndpointTests(unittest.TestCase):
    def test_declared_json_catalog_and_malformed_type(self):
        import json
        from product_tool.census.endpoint_probe import AccessProbe
        from product_tool.census.http_domain_discovery import HTTPDomainDiscovery
        for payload,expected_count in [({'@type':'ItemList','itemListElement':[{'item':{'@type':'Product','url':'https://example.com/products/ABC123','name':'ABC123'}}]},1),({'@type':[]},0)]:
            class Probe:
                def probe(self,url,**kw):
                    kw['request_guard'](url)
                    base=AccessProbe()._result(url,kw['capability'],kw['sample_type'],AccessStatus.DIRECT_ACCESS,200,(url,),url)
                    if url.endswith('/catalog.json'):return replace(base,content_type='application/json',diagnostic_text=json.dumps(payload))
                    if '/products/' in url:return replace(base,diagnostic_text='<script type="application/ld+json">{"@type":"Product","model":"ABC123"}</script>')
                    return replace(base,diagnostic_text='')
            d=replace(load_domains()[0],url='https://example.com/',page_hosts=('example.com',),support_hosts=(),capabilities={'structured_endpoints':['https://example.com/catalog.json']})
            r=HTTPDomainDiscovery(probe=Probe())(d,identity(),MultiDomainBudget(),10)
            self.assertEqual(len(r['candidates']),expected_count)
            if expected_count:self.assertEqual(r['candidates'][0]['identity_verification']['level'],'exact_model')

if __name__=='__main__':unittest.main()
