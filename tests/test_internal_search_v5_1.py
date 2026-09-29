import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from dataclasses import replace
from product_tool.census.internal_search_strategy import InternalSearchStrategy, CHECKPOINT_VERSIONS, parse_search_results, internal_search_readiness
from product_tool.census.search_routes import SearchHTMLParser
from product_tool.census.search_results import path_signals
from product_tool.census.search_snapshots import SearchSnapshotStore, sanitize_html
from test_internal_search_v1 import BASE, CONFIG, identity, pages, run, FakeProbe

FIX=Path(__file__).parent/'fixtures/stage5_1'


def parse(html,**kwargs):
    return parse_search_results(html,response_url=BASE+'search',expected=identity(),source_family='example',allowed_hosts=('example.com',),**kwargs)


class AdmissionTests(unittest.TestCase):
    def test_wrappers_are_not_cards_and_local_markers_are(self):
        html=(FIX/'results.html').read_text(encoding='utf-8-sig')
        audit={};found=parse(html,audit=audit)
        self.assertEqual({c.url for c in found},{BASE+'products/ABC-123',BASE+'device-detail',BASE+'special-device'})
        self.assertGreaterEqual(audit['navigation_service_excluded'],8)
        kinds={e['type'] for c in found for e in c.discovery_evidence}
        self.assertIn('html_product_card',kinds);self.assertIn('json_ld_itemlist_product',kinds)

    def test_full_path_segments(self):
        for path in ['support/product-support/manuals','product-support/item','support/products/item','pages/item','blogs/item','news/item','policies/item','about/item','contact-us','returns-policy','warranty/item','delivery/item','']:
            self.assertFalse(path_signals(BASE+path)[0],path)
            self.assertFalse(parse(f'<a href="/{path}">Plain link</a>'),path)
        for path in ['product/a','products/a','p/a','mkt-product/a']:
            self.assertTrue(path_signals(BASE+path)[0]);self.assertEqual(len(parse(f'<a href="/{path}">Device</a>')),1)

    def test_service_exception_requires_exact_model_reason(self):
        c=parse('<a href="/support/manual-ABC-123">Manual ABC-123</a>')[0]
        self.assertIn('service_path_retained_only_for_exact_model:-30',c.ranking_reasons)
        self.assertNotIn('product_like_path:+25',c.ranking_reasons)
        self.assertFalse(c.identity_verification)

    def test_first_party_brand_and_category_are_not_admission(self):
        self.assertFalse(parse('<a href="/example-brand">Example</a>',category_hints=('example',)))

    def test_itemlist_generic_navigation_does_not_get_product_bonus(self):
        html='<script type="application/ld+json">{"@type":"ItemList","itemListElement":[{"item":{"url":"/brand-story","name":"ABC-123"}}]}</script>'
        c=parse(html)[0]
        self.assertFalse(any(e['type']=='json_ld_itemlist_product' for e in c.discovery_evidence))
        self.assertTrue(any(e['type']=='exact_model_in_result_title' for e in c.discovery_evidence))
        self.assertFalse(c.identity_verification)

    def test_nearest_card_and_navigation_boundary(self):
        p=SearchHTMLParser();p.feed('<div class="product-card"><div class="product-item"><a href="/a">a</a></div><nav><a href="/b">b</a></nav></div>')
        self.assertEqual(p.links[0]['card_evidence']['marker'],'product-item')
        self.assertFalse(p.links[1]['card_evidence'])

    def test_configured_prefix_separate_evidence(self):
        c=parse('<a href="/devices/detail/xyz">Device</a>',configured_product_patterns=('/devices/detail/',))[0]
        self.assertTrue(any(e['type']=='configured_product_pattern' for e in c.discovery_evidence))
        self.assertFalse(any(e['type']=='html_product_card' for e in c.discovery_evidence))

    def test_schema_product_marker(self):
        self.assertEqual(len(parse('<div itemtype="https://schema.org/Product"><a href="/special">Thing</a></div>')),1)


class CheckpointTests(unittest.TestCase):
    def test_every_semantic_version_is_required(self):
        cp=run(FakeProbe(pages())).checkpoint
        for key in CHECKPOINT_VERSIONS:
            old=copy.deepcopy(cp);old[key]='old'
            result=run(FakeProbe({}),checkpoint=old)
            self.assertEqual(result.stop_reason,'checkpoint_incompatible')
            self.assertFalse(result.candidates)
        old=copy.deepcopy(cp)
        for key in CHECKPOINT_VERSIONS:old.pop(key)
        self.assertEqual(run(FakeProbe({}),checkpoint=old).stop_reason,'checkpoint_incompatible')

    def test_compatible_resume_no_requests(self):
        cp=run(FakeProbe(pages())).checkpoint;p=FakeProbe({})
        self.assertEqual(run(p,checkpoint=cp).stop_reason,'checkpoint_complete');self.assertFalse(p.calls)

    def test_missing_snapshots_explicit(self):
        cp=run(FakeProbe(pages())).checkpoint
        p=FakeProbe({});r=run(p,checkpoint=cp,reprocess=True)
        self.assertEqual(r.stop_reason,'snapshot_missing');self.assertFalse(p.calls)

    def test_ranking_configuration_is_compatibility_input(self):
        cp=run(FakeProbe(pages())).checkpoint
        self.assertEqual(run(FakeProbe({}),checkpoint=cp,configured_product_patterns=('/custom/',)).stop_reason,'checkpoint_incompatible')


class SnapshotTests(unittest.TestCase):
    def test_reprocess_rebuilds_old_candidates_without_network(self):
        with tempfile.TemporaryDirectory() as d:
            store=SearchSnapshotStore(Path(d)/'snapshots.sqlite3')
            original=run(FakeProbe(pages()),snapshot_writer=store.writer(identity(),'demo'))
            old=copy.deepcopy(original.checkpoint);old['result_parser_version']='old'
            old['candidates']=[];old['routes']=[];old['completed_queries']=[]
            before=hashlib.sha256(store.path.read_bytes()).hexdigest()
            p=FakeProbe({});r=run(p,checkpoint=old,reprocess=True,snapshot_loader=store.load)
            self.assertEqual(r.stop_reason,'exact_model_found');self.assertEqual(r.budget_used.http_requests,0);self.assertFalse(p.calls)
            self.assertEqual(r.checkpoint['result_parser_version'],CHECKPOINT_VERSIONS['result_parser_version'])
            self.assertNotIn('<script',json.dumps(r.checkpoint))
            self.assertFalse(internal_search_readiness(r)['production_ready'])
            self.assertEqual(before,hashlib.sha256(store.path.read_bytes()).hexdigest())

    def test_target_snapshot_missing_never_uses_old_identity(self):
        with tempfile.TemporaryDirectory() as d:
            store=SearchSnapshotStore(Path(d)/'snapshots.sqlite3')
            cp=run(FakeProbe(pages()),snapshot_writer=store.writer(identity(),'demo')).checkpoint
            cp=copy.deepcopy(cp);cp['snapshots']=[r for r in cp['snapshots'] if r['sample_type']!='internal_search_candidate']
            r=run(FakeProbe({}),checkpoint=cp,reprocess=True,snapshot_loader=store.load)
            self.assertEqual(r.stop_reason,'snapshot_missing');self.assertFalse(any(c.identity_verification for c in r.candidates))

    def test_content_hash_verified(self):
        with tempfile.TemporaryDirectory() as d:
            store=SearchSnapshotStore(Path(d)/'snapshots.sqlite3')
            cp=run(FakeProbe(pages()),snapshot_writer=store.writer(identity(),'demo')).checkpoint
            cp=copy.deepcopy(cp);cp['snapshots'][0]['content_sha256']='bad'
            r=run(FakeProbe({}),checkpoint=cp,reprocess=True,snapshot_loader=store.load)
            self.assertEqual(r.stop_reason,'snapshot_missing');self.assertIn('snapshot_hash_mismatch',r.errors)

    def test_hyperx_exact_model_requires_target_product(self):
        e=replace(identity(),brand_raw='HyperX',brand_canonical='hyperx',seller_sku='4P5D4AA',model_candidates=('4P5D4AA',))
        data={BASE+'search?q=4P5D4AA':'<a href="/products/cloud-alpha">4P5D4AA</a>',BASE+'products/cloud-alpha':(FIX/'hyperx_product.html').read_text(encoding='utf-8-sig')}
        with tempfile.TemporaryDirectory() as d:
            store=SearchSnapshotStore(Path(d)/'snapshots.sqlite3')
            cp=run(FakeProbe(data),expected=e,snapshot_writer=store.writer(e,'demo')).checkpoint
            r=run(FakeProbe({}),expected=e,checkpoint=cp,reprocess=True,snapshot_loader=store.load)
            self.assertEqual(r.stop_reason,'exact_model_found');self.assertEqual(r.budget_used.http_requests,0)

    def test_snapshot_sanitization(self):
        text=sanitize_html('<script>token="secret"</script><input name=csrf value=secret><a href="/products/a?email=private@example.com&_sid=secret">Device</a>')
        self.assertNotIn('secret',text);self.assertNotIn('private@example.com',text)



class FinalQualityTests(unittest.TestCase):
    def test_search_echo_is_not_a_product(self):
        audit={}
        self.assertFalse(parse('<a href="/search?q=ABC-123&type=product">ABC-123</a>',audit=audit))
        self.assertEqual(audit['rejected_links'][0]['reason'],'search_route_not_product')

    def test_personal_query_is_not_persisted(self):
        audit={};found=parse('<a href="/products/a?email=private@example.com">ABC-123</a>',audit=audit)
        self.assertFalse(found);self.assertNotIn('private@example.com',json.dumps(audit))

    def test_result_title_model_never_proves_identity(self):
        result=run(FakeProbe(pages('<h1>ABC-123</h1>')))
        self.assertEqual(result.stop_reason,'results_identity_insufficient')

    def test_multiple_products_can_share_isolated_snapshot_db(self):
        with tempfile.TemporaryDirectory() as d:
            store=SearchSnapshotStore(Path(d)/'snapshots.sqlite3')
            store.writer(identity(),'demo')
            store.writer(replace(identity(),seller_sku='OTHER-123'),'other')

    def test_snapshot_missing_resume_does_not_fall_back_to_network(self):
        with tempfile.TemporaryDirectory() as d:
            store=SearchSnapshotStore(Path(d)/'snapshots.sqlite3')
            cp=run(FakeProbe(pages()),snapshot_writer=store.writer(identity(),'demo')).checkpoint
            cp=copy.deepcopy(cp);cp['snapshots']=[x for x in cp['snapshots'] if x['sample_type']!='internal_search_candidate']
            missing=run(FakeProbe({}),checkpoint=cp,reprocess=True,snapshot_loader=store.load)
            self.assertEqual(run(FakeProbe({}),checkpoint=missing.checkpoint).stop_reason,'snapshot_missing')

    def test_versions_and_full_stage_baselines_unchanged(self):
        root=Path(__file__).resolve().parents[1]
        before_path=root/'reports/source_census_2026-09-22_stage5_1/protected_hashes_before.json'
        if not before_path.exists():self.skipTest('Live baseline manifest is not installed')
        from _pipeline_migration import ALL_AUTHORIZED_CHANGES, check_migrated_file
        before=json.loads(before_path.read_text(encoding='utf-8'))
        for path,digest in before.items():
            actual=hashlib.sha256((root/path).read_bytes()).hexdigest()
            normalized=path.replace('\\','/')
            if normalized in ALL_AUTHORIZED_CHANGES:
                ok,msg=check_migrated_file(normalized,actual)
                self.assertTrue(ok,msg)
                continue
            self.assertEqual(actual,digest,path)


class SnapshotSecretTests(unittest.TestCase):
    def test_meta_and_unknown_hidden_values_are_omitted(self):
        text=sanitize_html('<meta name="csrf-token" content="secret-value"><input type=hidden name=opaque_field value="secret-value"><div data-config="secret-value">Product</div>')
        self.assertNotIn('secret-value',text)

if __name__=='__main__':unittest.main()
