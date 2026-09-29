"""Fixture-based structural census regression tests; network is never required."""
from pathlib import Path
import copy
import json
import tempfile
import unittest
from unittest.mock import patch
from product_tool.census.structural_contracts_v8 import inspect_structure,cluster_profiles,LAYERS
from product_tool.census.structural_runner_v8 import Sampler,profile,protected
from product_tool.census.structural_inventory_v8 import inventory,OUTPUT,ROOT
from _source_policy import unapproved_source_ids

FIXTURE='''<html><script src="/etc.clientlibs/site.js"></script><script type="application/ld+json">{"@type":"Product","name":"Example PHONE","mpn":"MODEL-123","gtin13":"1234567890123","color":"black","image":{"@type":"ImageObject","contentUrl":"https://brand.test/img1.jpg"},"additionalProperty":[{"@type":"PropertyValue","name":"Power","value":"50"}]}</script><main id="random-a91"><a href="/products/model-123">Example phone</a><table><tr><th>Power</th><td>50</td></tr></table><img srcset="/small.jpg 300w, /large.jpg 1200w"><a href="/support/model-123/manual.pdf" hreflang="en">Manual</a></main></html>'''

def inspected(html=FIXTURE):return inspect_structure(html,'https://brand.test/en/product',('brand.test',))

def make_profile(pid='one',family='brand_a',review=True,structure=None):
    obj=structure or inspected()
    return {'profile_id':pid,'source_family':family,'official_domain':'https://'+pid+'.test/en/','sample_product_page':'https://'+pid+'.test/en/product','completeness_status':'adapter_profile_complete','layers':{l:{'observed':obj['observed'][l],'signature':obj['signatures'][l],'contract':obj['contracts'][l],'fixture':'fixture_'+pid+'.json','contract_reviewed':review} for l in LAYERS}}

class StructuralCensusTests(unittest.TestCase):
    def test_values_and_css_ids_do_not_change_signature(self):
        changed=FIXTURE.replace('MODEL-123','OTHER-999').replace('Example PHONE','Other TV').replace('random-a91','hash-b282').replace('black','white').replace('1234567890123','9999999999999').replace('50','300')
        self.assertEqual(inspected()['signatures'],inspected(changed)['signatures'])
    def test_CMS_without_contract_is_not_shared(self):
        obj=inspected('<script src="/etc.clientlibs/site.js"></script>')
        profiles=[make_profile('a','a',structure=obj),make_profile('b','b',structure=obj)]
        self.assertTrue(all(not groups for groups in cluster_profiles(profiles).values()))
    def test_field_set_with_incompatible_identity_not_merged(self):
        a=make_profile();b=make_profile('two','brand_b')
        b['layers']['identity']['contract']['model_semantics']='unverified_sku_meaning'
        self.assertEqual(len(cluster_profiles([a,b])['identity']),2)
    def test_layers_can_have_different_families(self):
        a=make_profile();b=make_profile('two','brand_b')
        b['layers']['documents']['signature']='different'
        c=cluster_profiles([a,b]);self.assertEqual(len(c['identity']),1);self.assertEqual(len(c['documents']),2)
    def test_regional_requires_review_and_fixtures(self):
        a=make_profile();b=make_profile('two','brand_a',review=False)
        self.assertTrue(all(x['status']=='custom_adapter_candidate' for x in cluster_profiles([a,b])['identity']))
        b=make_profile('two','brand_a');self.assertEqual(cluster_profiles([a,b])['identity'][0]['status'],'regional_shared_candidate')
    def test_single_source_stays_custom_and_not_production(self):
        for groups in cluster_profiles([make_profile()]).values():
            for c in groups:self.assertEqual(c['status'],'custom_adapter_candidate');self.assertFalse(c['production_ready'])
    def test_blocked_js_only_no_invented_contract(self):
        for status in ['http_blocked','javascript_only']:
            p=make_profile();p['completeness_status']=status
            self.assertTrue(all(not groups for groups in cluster_profiles([p]).values()))
    def test_snapshot_avoids_probe(self):
        item={'url':'https://brand.test/','origin':'existing_snapshot'}
        sampler=Sampler({item['url']:item},[],live=True)
        with patch.object(sampler.probe,'probe',side_effect=AssertionError('network')):
            self.assertIs(sampler.fetch({'url':item['url'],'kind':'homepage','provenance':{}},{'profile_id':'a','allowed_hosts':['brand.test']}),item)
    def test_list_of_products_not_a_product_page(self):
        self.assertFalse(inspected('<script type="application/ld+json">[{"@type":"Product","name":"A"},{"@type":"Product","name":"B"}]</script>')['is_product_page'])
    def test_no_sensitive_fields_in_paths(self):
        obj=inspected(FIXTURE.replace('"mpn":"MODEL-123"','"mpn":"MODEL-123","session_token":"SECRET","customer_email":"mail@example.com"'))
        self.assertNotIn('session_token',json.dumps(obj['contracts']));self.assertNotIn('mail@example',json.dumps(obj['contracts']))
    def test_inventory_complete_and_exclusions(self):
        records,labels,families,missing,totals=inventory()
        self.assertFalse(missing);self.assertEqual(len(labels),289)
        self.assertEqual(len({r['profile_id'] for r in records}),len(records))
        catalog=json.loads((ROOT/'product_tool/config/source_catalog.v2.json').read_text(encoding='utf-8'))
        self.assertEqual(unapproved_source_ids(s['source_id'] for s in catalog['sources']),set())
        # any non-official (dealer) source present in the inventory must be an approved one
        non_official={s['source_id'] for s in catalog['sources'] if s['official_status']!='official_verified'}
        self.assertEqual(unapproved_source_ids(non_official&{r['source_family'] for r in records}),set())
        self.assertTrue({'hyperx','hiper','bosch_home','bosch_tools'}<={r['source_family'] for r in records})
    def test_confirmed_challenge_stops_host(self):
        self.assertTrue(protected({'protection_status':'challenge_confirmed','http_status':200}))
        self.assertFalse(protected({'protection_status':'challenge_suspected','http_status':200}))
    def test_persisted_host_budget_counts_redirects(self):
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)
            attempts=[{'url':'https://brand.test/old'+str(i),'profile_id':'old'} for i in range(7)]
            (output/'http_attempts.json').write_text(json.dumps(attempts),encoding='utf-8')
            class Probe:
                def probe(self,url,**kw):
                    kw['request_guard'](url)
                    kw['request_guard']('https://brand.test/redirect')
            with patch('product_tool.census.structural_runner_v8.OUTPUT',output):
                sampler=Sampler({},[],live=True,probe=Probe())
                with self.assertRaisesRegex(RuntimeError,'bounded_sampling_limit'):
                    sampler.fetch({'url':'https://brand.test/','kind':'homepage','provenance':{}},{'profile_id':'new','allowed_hosts':['brand.test']})
                self.assertEqual(len(sampler.attempts),8)
    def test_dealer_product_needs_existing_LG_scope(self):
        sampler=Sampler({},[],live=True)
        with self.assertRaisesRegex(RuntimeError,'LG_appliance_scope'):
            sampler.fetch({'url':'https://sulpak.kz/unknown','kind':'product','provenance':{}},{'profile_id':'sulpak','source_family':'sulpak','allowed_hosts':['sulpak.kz']})
    def test_schema_rejects_production_ready(self):
        from product_tool.census.structural_schema_v8 import validate_schema
        schema=json.loads((OUTPUT/'adapter_profiles.v1.schema.json').read_text(encoding='utf-8'))
        with self.assertRaises(ValueError):validate_schema({'schema_version':1,'production_ready':True,'profiles':[]},schema)

    def test_locale_switcher_is_not_a_document_or_document_language(self):
        obj=inspected('<a href="/fr/" hreflang="fr">French</a>')
        self.assertFalse(obj['observed']['documents'])
        obj=inspected('<a href="/fr/" hreflang="fr">French</a><a href="/manual.pdf">Manual</a>')
        self.assertEqual(obj['contracts']['documents']['language_contract'],'unknown_do_not_infer_from_locale')

    def test_actual_profiles_schema_and_fixture_contracts(self):
        from product_tool.census.structural_schema_v8 import validate_schema
        from product_tool.census.structural_report_v8 import contract_review
        data=json.loads((OUTPUT/'adapter_profiles.v1.json').read_text(encoding='utf-8'))
        schema=json.loads((OUTPUT/'adapter_profiles.v1.schema.json').read_text(encoding='utf-8'))
        validate_schema(data,schema)
        contract_review(data['profiles'])
        self.assertEqual(len(data['profiles']),127)
        self.assertTrue(all(not p['production_ready'] and p['next_action'] for p in data['profiles']))
    def test_actual_HTTP_caps_and_no_catalog_queries(self):
        from collections import Counter
        from urllib.parse import urlsplit
        attempts=json.loads((OUTPUT/'http_attempts.json').read_text(encoding='utf-8'))
        self.assertLessEqual(len(attempts),500)
        self.assertLessEqual(max(Counter(urlsplit(a['url']).hostname for a in attempts).values()),8)
        self.assertLessEqual(max(Counter(a['profile_id'] for a in attempts).values()),5)
        self.assertTrue(all(a['access_method']=='http' and a['sample_kind']!='internal_search' for a in attempts))
        self.assertFalse(any(a['profile_id']=='sulpak' for a in attempts))
    def test_all_labels_accounted_for_and_Xiaomi_priority_verified(self):
        matrix=json.loads((OUTPUT/'adapter_matrix.json').read_text(encoding='utf-8'))
        self.assertEqual(len(matrix['brand_label_mapping']),289)
        self.assertTrue(all(x['next_action'] and x['stage8_status']!='research_pending' for x in matrix['brand_label_mapping']))
        xiaomi=next(x for x in matrix['priority_brand_map'] if x['source_family']=='xiaomi_global')
        self.assertTrue(xiaomi['profile_ids'])

    def test_protected_registries_unchanged(self):
        import hashlib
        from _pipeline_migration import ALL_AUTHORIZED_CHANGES, check_migrated_file
        before=json.loads((OUTPUT/'protected_hashes_before.json').read_text(encoding='utf-8'))
        for path,digest in before.items():
            if path.startswith('product_tool/config/'):
                actual=hashlib.sha256((ROOT/path).read_bytes()).hexdigest()
                if path in ALL_AUTHORIZED_CHANGES:
                    ok,msg=check_migrated_file(path,actual)
                    self.assertTrue(ok,msg)
                    continue
                self.assertEqual(actual,digest)

if __name__=='__main__':unittest.main()
