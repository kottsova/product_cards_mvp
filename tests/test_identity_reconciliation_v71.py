"""Stage 7.1 regression tests use fixtures and immutable offline observations only."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import unittest
import tempfile
import inspect

class Parameterize:
    @staticmethod
    def parametrize(names, rows):
        def decorate(fn):
            def run():
                for args in rows:
                    fn(*args)
            return run
        return decorate

class TestParameters:
    mark = Parameterize()

pytest = TestParameters()
from openpyxl import Workbook
from product_tool.identity import PageIdentity, IdentityVerifier, VariantAttributes
from product_tool.census.catalog_identity import reconcile, as_identity, load_rows, scope_key, rules
from product_tool.census.structured_identity_v71 import verify_page
from product_tool.census.runner_v71 import query_coverage, replay_domain, decide, BoundedHTTP
from product_tool.census.official_domains import load_domains
from product_tool.census.scoped_access import AccessLedger, AccessObservation


def row(brand='Samsung', title='Jet 70 Turbo (VS15T7031R4/EV)', sku='Jet_70_turbo/(VS15T7031R4/EV)', **kw):
    return dict(brand_raw=brand, category_raw='vacuum', seller_sku_raw=sku, wb_sku_raw='99999999', title_raw=title, alternate_titles_raw=None, alternate_code_raw=None, original_row={'original': title}, row_reference='Products!A2:H2', **kw)


def test_full_original_catalog_row_read_only(tmp_path):
    path = tmp_path/'catalog.xlsx'
    book = Workbook(); sheet = book.active; sheet.title = '\u0422\u043e\u0432\u0430\u0440\u044b'
    sheet.append(['brand','category','sku','wb','title','alt_title','tnved','repeats'])
    sheet.append(['Samsung','vacuum','SKU','999','Real Jet 70 Turbo VS15T7031R4/EV',None,'0000',1]); book.save(path)
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    with patch('product_tool.census.catalog_identity.load_workbook', wraps=__import__('openpyxl').load_workbook) as loader:
        record = reconcile(load_rows(path, ['SKU'])['SKU'])
        assert loader.call_args.kwargs == {'read_only': True, 'data_only': True}
    assert record['title_raw'].startswith('Real Jet') and record['rows'][0]['original_row']['tnved'] == '0000'
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


def test_composite_title_codes_regions_and_wb():
    r = reconcile([row()]); queries = [q['query'] for q in r['queries']]
    assert queries == ['VS15T7031R4/EV', 'JET 70 TURBO']
    assert r['identity']['seller_sku'] == 'Jet_70_turbo/(VS15T7031R4/EV)'
    assert '99999999' not in queries and all('TURBO/' not in q for q in queries)
    assert r['identity']['variant_attributes']['region'] == 'EV'
    assert r['candidates'][0]['significant_punctuation'] == '/'
    assert not query_coverage([dict(query=queries[0], checked=True)], r['high_confidence_candidates'])


def test_parentheses_priority():
    r = reconcile([row(title='WD10T654CBH/LD (VS15T7031R4/EV)')])
    assert r['queries'][0]['query'] == 'VS15T7031R4/EV'


@pytest.mark.parametrize('brand,title,sku,variant', [('BOSCH','Bosch SBV45FX01R/01','SBV45FX01R/01',{'service_index':'01'}),('Karcher','FC 7 Cordless, 1.055-701.0','1.055-701.0',{})])
def test_brand_punctuation(brand,title,sku,variant):
    r = reconcile([row(brand,title,sku)])
    assert r['queries'][0]['query'] == sku
    assert r['identity']['variant_attributes'] == variant


def test_dreame_internal_is_not_manufacturer():
    r = reconcile([row('Dreame','Wet vacuum G10, HHR12A','HHR12A')])
    assert r['identity']['model_candidates'] == ()
    assert r['identity']['marketing_models'] == ('G10',)
    assert next(c for c in r['candidates'] if c['raw_value']=='HHR12A')['role'] == 'possible_internal_code'


def test_ambiguity_retains_all_titles_and_blocks_scope():
    a = row(); a['alternate_titles_raw'] = 'Different title'
    r = reconcile([a]); assert len(r['titles_raw']) == 2 and r['title_raw'] is None
    assert r['review_status'] == 'ambiguous_catalog_identity'
    assert not query_coverage([{'query':q,'checked':True} for q in r['high_confidence_candidates']],r['high_confidence_candidates'],True)
    assert reconcile([row(),row()])['review_status'] == 'ambiguous_catalog_identity'


def test_specs_not_regional_suffix():
    r = reconcile([row(title='MNA114MS1CCX/114"/UHD/Smart TV/Wi-Fi/BT',sku='MNA114MS1CCX')])
    assert r['identity']['variant_attributes'] == {'screen_size':'114'}


def expected_dreame():
    return as_identity(reconcile([row('Dreame','Wet vacuum G10','HHR12A')]))


def domain():
    return next(d for d in load_domains() if d.source_family=='dreame')


def html(name, **fields):
    return '<script type="application/ld+json">'+json.dumps({'@type':'Product','name':name,**fields})+'</script>'


def test_structured_marketing_exact_and_body_not_evidence():
    expected = expected_dreame()
    assert verify_page(html('Dreame G10 wet vacuum'),expected,domain())['level'] == 'exact_model'
    assert verify_page('<body>Dreame G10 wet vacuum</body>',expected,domain())['level'] == 'insufficient'
    assert verify_page(html('Dreame G100 wet vacuum'),expected,domain())['level'] == 'insufficient'
    assert verify_page(html('Dreame G10 phone'),expected,domain())['level'] == 'insufficient'
    assert verify_page(html('Dreame G10 vacuum',brand='LG'),expected,domain())['level'] == 'insufficient'


def test_microdata_name_is_structured():
    page='<div itemscope itemtype="https://schema.org/Product"><span itemprop="name">Dreame G10 vacuum</span></div>'
    assert verify_page(page,expected_dreame(),domain())['level']=='exact_model'


def test_variants_missing_matching_conflicting_and_model_conflict():
    expected=replace(expected_dreame(), variant_attributes=VariantAttributes({'color':'BLACK'}))
    assert verify_page(html('Dreame G10 vacuum'),expected,domain())['level']=='exact_model'
    assert verify_page(html('Dreame G10 vacuum',color='black'),expected,domain())['level']=='exact_variant'
    assert verify_page(html('Dreame G10 vacuum',color='white'),expected,domain())['level']=='conflict'
    assert verify_page(html('Dreame G10 vacuum',model='OTHER'),expected,domain())['level']=='conflict'


def test_family_and_generic_word():
    expected=replace(expected_dreame(),marketing_models=('D20 PLUS',))
    assert verify_page(html('Dreame D20 vacuum'),expected,domain())['level']=='family_only'
    assert verify_page(html('Dreame Plus vacuum'),replace(expected,marketing_models=('PLUS',)),domain())['level']=='insufficient'


def test_legacy_page_positional_constructor():
    v=VariantAttributes({'color':'black'})
    assert PageIdentity('a','b','c','d','e',v).variant_attributes is v


def test_scope_versions_and_config_invalidate():
    r=reconcile([row()]); a=scope_key(r,[], 'hash')
    assert a!=scope_key(r,[], 'new_hash')
    assert a!=scope_key(dict(r,version='old'),[], 'hash')
    config=rules();config['version']='new'
    with patch('product_tool.census.catalog_identity.rules',return_value=config):
        assert a!=scope_key(r,[], 'hash')


def test_offline_replay_no_network_and_old_gate_rejected():
    d=domain(); r=reconcile([row('Dreame','Dreame G10 vacuum','HHR12A')])
    url=d.url.rstrip('/')+'/products/g10'
    previous={'candidates':[{'url':url}],'requests':[], 'queries':['HHR12A'], 'truncated':False,'outcome':'bounded_discovery_complete'}
    cache={url:{'response':{'http_status':200,'access_status':'direct_access','final_url':url},'content':html('Dreame G10 vacuum'),'snapshot':None}}
    with patch('socket.socket',side_effect=AssertionError('network forbidden')):
        result=replay_domain(d,previous,r,cache)
    assert result['candidates'][0]['identity_verification']['level']=='exact_model'
    assert not result['identity_query_scope_complete']
    assert not decide(r,[result],[d])['dealer_fallback']['allowed']


def test_no_old_absence_when_pending_or_truncated():
    r=reconcile([row('Dreame','Dreame G10 vacuum','HHR12A')]);d=domain()
    result={'domain_id':d.domain_id,'candidates':[],'identity_query_scope_complete':True,'unvalidated_candidates':False,'search_complete':False}
    assert decide(r,[result],[d])['outcome']=='official_search_incomplete'


def test_production_and_dealer_registry_unchanged():
    root=Path(__file__).resolve().parents[1]
    before=json.loads((root/'reports/source_census_2026-09-22_stage7_1/protected_hashes_before.json').read_text(encoding='utf-8'))
    # Manifest shape is checked separately by the report; registry bytes must never change.
    from _pipeline_migration import ALL_AUTHORIZED_CHANGES, check_migrated_file
    entries=before.get('files',before)
    if isinstance(entries,list):
        entries={x['path']:x['sha256'] for x in entries}
    for name,value in entries.items():
        normalized=name.replace('\\','/')
        if 'product_tool/config/' in normalized:
            digest=value.get('sha256') if isinstance(value,dict) else value
            actual=hashlib.sha256((root/name).read_bytes()).hexdigest()
            if normalized in ALL_AUTHORIZED_CHANGES:
                ok,msg=check_migrated_file(normalized,actual)
                assert ok,msg
                continue
            assert actual==digest


def test_marketing_qualifier_conflict():
    assert verify_page(html('Dreame G10 Pro vacuum'), expected_dreame(), domain())['level'] == 'conflict'


def test_http_preconditions_and_aggregate_redirect_cap(tmp_path):
    r = reconcile([row('Dreame','Dreame G10 vacuum','HHR12A')])
    q = next(q for q in r['queries'] if q['query'] == 'G10')
    expected = as_identity(r); d = domain(); ledger = AccessLedger()
    class Probe:
        def probe(self, url, **kwargs):
            kwargs['request_guard'](url)
            kwargs['request_guard'](url + '?redirect=1')
            raise AssertionError('guard must stop second redirect')
    http = BoundedHTTP({}, ledger, tmp_path, probe=Probe())
    with unittest.TestCase().assertRaisesRegex(ValueError, 'unsearched'):
        http.fetch(d.url, d, expected, q, old_queries={'G10'})
    assert http.count == 0
    http.count = 23
    with unittest.TestCase().assertRaisesRegex(RuntimeError, 'budget'):
        http.fetch(d.url, d, expected, q, old_queries=set())
    assert http.count == 24 and len(http.receipts) == 1


def test_http_endpoint_pause_is_method_scoped(tmp_path):
    expected = expected_dreame(); d = domain()
    q = next(q for q in reconcile([row('Dreame','Dreame G10 vacuum','HHR12A')])['queries'] if q['query']=='G10')
    from urllib.parse import urlsplit
    obs = AccessObservation(urlsplit(d.url).hostname,d.url,'http','internal_search','captcha_or_blocked','challenge_detected',403,'now')
    class Probe:
        def probe(self,url,**kwargs):
            kwargs['request_guard'](url)
            raise RuntimeError('passed_guard')
    ledger=AccessLedger([obs]);http=BoundedHTTP({},ledger,tmp_path,probe=Probe())
    with unittest.TestCase().assertRaisesRegex(RuntimeError,'protected_HTTP_endpoint'):
        http.fetch(d.url,d,expected,q,old_queries=set())
    assert http.count==0
    ledger.observations=[replace(obs,access_method='browser')]
    with unittest.TestCase().assertRaisesRegex(RuntimeError,'passed_guard'):
        http.fetch(d.url,d,expected,q,old_queries=set())
    assert http.count==1


def test_absent_service_index_is_missing_not_conflicting():
    expected = as_identity(reconcile([row('BOSCH','Bosch SBV45FX01R/01','SBV45FX01R/01')]))
    result = IdentityVerifier().verify(expected,PageIdentity(model_code='SBV45FX01R'),source='bosch')
    assert result.level.value == 'exact_model'
    assert IdentityVerifier().verify(expected,PageIdentity(model_code='SBV45FX01R/02'),source='bosch').level.value == 'conflict'


def test_multiple_marketing_models_do_not_establish_exact():
    assert verify_page(html('Dreame G10 / G20 vacuum'),expected_dreame(),domain())['level']=='conflict'


def test_http_success_alone_does_not_complete_query():
    from product_tool.census.runner_v71 import search_response_evidence
    item={'response':{'http_status':200,'access_status':'direct_access','final_url':domain().url},'content':'<html>Home search loading</html>'}
    assert not search_response_evidence(item,expected_dreame(),domain())


class IdentityReconciliationTests(unittest.TestCase):
    pass


def _adapt(fn):
    def run(self):
        if 'tmp_path' in inspect.signature(fn).parameters:
            with tempfile.TemporaryDirectory() as directory:
                fn(Path(directory))
        else:
            fn()
    return run


for _name, _fn in list(globals().items()):
    if _name.startswith('test_') and callable(_fn):
        setattr(IdentityReconciliationTests, _name, _adapt(_fn))

if __name__ == '__main__':
    unittest.main()
