"""Published-route discovery and independent hardware/retail negative controls."""
import unittest,json,tempfile,hashlib
from pathlib import Path
from unittest.mock import patch
import requests
from product_tool.adapters.xbox import XboxAdapter,_CACHE
from product_tool.adapters.policy_session import PolicyResponse
from product_tool.xbox_page import parse_page,assignment
from product_tool.xbox_identity import canonical_product_url
from product_tool import jobs,storage,card_evidence,xbox_pipeline

PID='ABCD1234EFGH';SKU='ZZ9Q';PDP='https://www.microsoft.com/en-us/d/xbox-series-s-2tb-white/'+PID.lower()
CAT='https://www.xbox.com/public/allConsoles.js'
def own(title='Xbox Series S',storage='2TB',model='',gallery=None,sku_id=SKU):
    images=gallery if gallery is not None else [dict(uri='https://cdn-dynmedia-1.microsoft.com/is/image/microsoftcorp/invented-white',alt='Xbox Series S console White')]
    product=dict(productId=PID,title=title,skuInfo={SKU:dict(skuId=sku_id,title=title,galleryImages=images)},galleryImages=images)
    return '<h1>'+title+'</h1><table><tr><td>Internal storage</td><td>'+storage+' Custom NVME SSD</td></tr><tr><td>CPU</td><td>Zen 2</td></tr><tr><td>Memory</td><td>10GB GDDR6</td></tr><tr><td>HDMI</td><td>HDMI 2.1</td></tr><tr><td>Wireless</td><td>802.11ac</td></tr>'+(('<tr><td>Support Period</td><td>Xbox Series S, Model Number '+model+'</td></tr>') if model else '')+'</table><script>window.__BuyBox__='+json.dumps({'product':product})+';</script>'
def binding(**updates):
    return dict(value=PID+'/'+SKU,source_url=CAT,title='Xbox Series S 2TB',region='en-US',storage='2TB',color='white',feature='digital',**updates)
def captured(url):
    digest=hashlib.sha256(url.encode()).hexdigest()[:20]
    for root in ['reports/xbox_stage69/observed','reports/xbox_stage69/live_initial/xbox_captures','reports/xbox_stage68/observed','reports/xbox_stage68/xbox_captures']:
        p=Path(root)/(digest+'.html')
        if p.exists():return p.read_text(encoding='utf8')
    raise AssertionError('Missing public source capture '+url)

class DiscoveryTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.log=Path(self.tmp.name)/'http.json'
    def tearDown(self):self.tmp.cleanup()
    def adapter(self,pages):
        self.calls=[]
        class Session:
            def get(inner,u,**kwargs):
                self.calls.append(u);v=pages.get(u)
                if isinstance(v,Exception):raise v
                if isinstance(v,list):v=v.pop(0)
                return v if isinstance(v,PolicyResponse) else PolicyResponse(u,200,v) if v else PolicyResponse(u,404,'not found')
        class Search:
            def search_provider(inner,*args):raise AssertionError('External search before successful official discovery')
            def close(inner):pass
        return XboxAdapter(fetch_log_path=self.log,session=Session(),search_factory=Search)
    def test_invented_commercial_configuration_from_declared_catalog(self):
        catalog={'locales':{'en-us':[dict(headline='Xbox Series S 2TB',detailsURL=PDP,gaPid=PID+'/'+SKU,storage='2TB',color='white',feature='digital')]}}
        a=self.adapter({'https://www.xbox.com/en-us/consoles/xbox-series-s':'<h1>Xbox Series S</h1><script src="'+CAT+'"></script>',CAT:'allConsoles='+json.dumps(catalog),PDP.lower():own()})
        d=a.find_source('Xbox Series S 2TB',name='Xbox Series S 2TB White',region='en-US',deadline=a.clock()+30)
        e=a.reports['XBOX SERIES S 2TB'];self.assertEqual(e['identity']['configuration'],'published_catalog_configuration');self.assertEqual(e['identifiers']['store_sku_id'],SKU);self.assertTrue(d.photos)
    def test_missing_catalog_item_discovered_via_own_searchaction(self):
        root='https://www.microsoft.com/en-us';search=root+'/search/explore?q='+PID
        pages={root:'<script type="application/ld+json">'+json.dumps(dict(potentialAction={'@type':'SearchAction','target':{'urlTemplate':root+'/search/explore?q={search_term_string}'}}))+'</script>',search:'<a href="'+PDP+'">Xbox Series S</a>',PDP.lower():own()}
        a=self.adapter(pages);d=a.find_source(PID,name='Xbox Series S 2TB White',region='en-US',deadline=a.clock()+30);self.assertEqual(d.source_key,'xbox_configuration');self.assertIn(search,self.calls)
    def test_network_failure_retries_same_url_once(self):
        pages={PDP:[requests.ConnectionError('temporary'),PolicyResponse(PDP,200,own())]};a=self.adapter(pages)
        # A session exception occurs before its response; shared retry sees it.
        class Session:
            def get(inner,u,**kwargs):
                self.calls.append(u);v=pages[u].pop(0)
                if isinstance(v,Exception):raise v
                return v
        a.session=Session();self.assertIsNotNone(a.fetch(PDP,PID,'store','product',a.clock()+30));self.assertEqual(self.calls,[PDP,PDP])
    def test_429_is_not_retried_or_cached(self):
        a=self.adapter({PDP:PolicyResponse(PDP,429,'stop')});self.assertIsNone(a.fetch(PDP,PID,'store','product',a.clock()+30));self.assertEqual(self.calls,[PDP]);self.assertNotIn((str(self.log),PDP),_CACHE)
    def test_tracking_and_fragment_do_not_spend_candidate_slots(self):
        self.assertEqual(canonical_product_url(PDP+'?icid=abc&bnplprovider=paypal#FAQ'),PDP.lower())
    def test_uk_declared_custom_search_route_links_hardware(self):
        root='https://www.microsoft.com/en-gb';pdp=PDP.replace('en-us','en-gb');q=root+'/search/explore?q=1883'
        a=self.adapter({root:'<uhf-search searchUrl="'+root+'/search/explore" queryParameterName="q"></uhf-search>',q:'<a href="'+pdp+'">Xbox Series S</a>',pdp.lower():own(model='1883')})
        d=a.find_source('1883',name='Xbox Series S hardware model 1883',region='en-GB',deadline=a.clock()+30);self.assertEqual(d.source_key,'xbox_hardware');self.assertTrue(a.reports['1883']['hardware_complete']);self.assertIn(q,self.calls)
    def test_attended_google_site_is_bound_to_official_hosts(self):
        from product_tool.census.attended_google import google_search_url
        hosts=('www.xbox.com','www.microsoft.com');self.assertTrue(google_search_url('https://www.google.com/search?q=site:microsoft.com%20Xbox',hosts));self.assertFalse(google_search_url('https://www.google.com/search?q=site:evil.com%20Xbox',hosts));self.assertTrue(google_search_url('https://www.google.com/search?q=site:lg.com%20LG'))
    def test_hardware_number_miss_falls_back_to_normalized_model_query(self):
        root='https://www.microsoft.com/en-gb';pdp=PDP.replace('en-us','en-gb');q=root+'/search/explore?q=Xbox%20Series%20S'
        a=self.adapter({root:'<uhf-search searchUrl="'+root+'/search/explore" queryParameterName="q"></uhf-search>',root+'/search/explore?q=1883':'<p>Replacement parts only</p>',q:'<a href="'+pdp+'">Xbox Series S</a>',pdp.lower():own(model='1883')})
        d=a.find_source('1883',name='Xbox Series S hardware model 1883',region='en-GB',deadline=a.clock()+30)
        self.assertEqual(d.source_key,'xbox_hardware');self.assertIn(q,self.calls)
    def test_duplicate_display_url_preserves_title_for_opaque_product_slug(self):
        root='https://www.microsoft.com/en-gb';pdp=root+'/d/product-name/'+PID.lower();q=root+'/search/explore?q=1883'
        a=self.adapter({root:'<uhf-search searchUrl="'+root+'/search/explore" queryParameterName="q"></uhf-search>',q:'<a href="'+pdp+'">Buy Xbox Series S</a><a href="'+pdp+'">'+pdp+'</a>',pdp:own(model='1883')})
        d=a.find_source('1883',name='Xbox Series S hardware model 1883',region='en-GB',deadline=a.clock()+30);self.assertEqual(d.source_key,'xbox_hardware')

class ScopeTests(unittest.TestCase):
    def test_console_gallery_accessory_only_is_candidate(self):
        images=[dict(uri='https://cdn-dynmedia-1.microsoft.com/is/image/microsoftcorp/accessory',alt='Xbox Series S Controller')]
        d,e=parse_page(own(gallery=images),PDP,PID,'series_s','en-US')
        self.assertFalse(d.photos);self.assertTrue(e['photo_candidates'])
    def test_name_and_specs_alone_do_not_select_catalog_configuration(self):
        d,e=parse_page(own(),PDP,'Xbox Series S 2TB','series_s','en-US',name='Xbox Series S 2TB White');self.assertFalse(e['configuration_complete'])
    def test_catalog_wrong_storage_rejected(self):
        c=binding();c['storage']='1TB';d,e=parse_page(own(),PDP,'Xbox Series S 2TB','series_s','en-US',name='Xbox Series S 2TB White',catalog_bindings=[c]);self.assertFalse(e['configuration_complete'])
    def test_catalog_other_region_rejected(self):
        c=binding();c['region']='en-GB';d,e=parse_page(own(),PDP,'Xbox Series S 2TB','series_s','en-US',name='Xbox Series S 2TB White',catalog_bindings=[c]);self.assertFalse(e['configuration_complete'])
    def test_catalog_stale_sku_row_rejected(self):
        d,e=parse_page(own(sku_id='BAD1'),PDP,'Xbox Series S 2TB','series_s','en-US',name='Xbox Series S 2TB White',catalog_bindings=[binding()]);self.assertFalse(e['configuration_complete'])
    def test_hardware_number_is_not_unique_retail_variant(self):
        url=PDP.replace('en-us','en-gb');d,e=parse_page(own(model='1883'),url,'1883','series_s','en-GB')
        self.assertEqual(d.source_key,'xbox_hardware');self.assertTrue(e['hardware_complete']);self.assertFalse(e['configuration_complete']);self.assertFalse(e['configuration_fields']);self.assertNotIn('store_product_id',e['identifiers']);self.assertEqual(e['identity_relations'][0]['product_id'],PID);self.assertTrue(d.photos);self.assertFalse(any(x.name=='Встроенный накопитель' for x in d.attributes))
    def test_adjacent_hardware_number_rejected(self):
        d,e=parse_page(own(model='18830'),PDP,'1883','series_s','en-US');self.assertFalse(e['hardware_complete']);self.assertFalse(d.photos)
    def test_white_source_gallery_explicit_black_remains_candidate(self):
        images=[dict(uri='https://cdn-dynmedia-1.microsoft.com/is/image/microsoftcorp/black',alt='Xbox Series S console Carbon Black')];d,e=parse_page(own(title='Xbox Series S 2TB White',gallery=images),PDP,PID,'series_s','en-US');self.assertFalse(d.photos);self.assertTrue(e['photo_candidates'])
    def test_other_named_bundle_gallery_is_not_exact(self):
        images=[dict(uri='https://cdn-dynmedia-1.microsoft.com/is/image/microsoftcorp/other',alt='Xbox Series S Forza Bundle')];d,e=parse_page(own(title='Xbox Series S Diablo IV Bundle',gallery=images),PDP,PID,'series_s','en-US');self.assertFalse(d.photos);self.assertTrue(e['photo_candidates'])
    def test_bundle_caption_belongs_to_own_bundle(self):
        u='https://www.microsoft.com/en-us/d/xbox-series-x-diablo-iv-bundle/8n1bb8dsbknt';d,e=parse_page(captured(u),u,'8N1BB8DSBKNT','series_x','en-US');self.assertTrue(d.photos);self.assertTrue(all(s['kind']=='bundle_gallery' for s in e['photo_scopes'].values()));self.assertNotIn('game_pass',e['configuration_fields'])
    def test_cpu_continuation_is_not_dropped(self):
        h='<div><h1>Xbox Series X</h1><table><tr><td>Processor</td><td>CPU: 8X Cores @ 3.8 GHz (<br>3.6 GHz w/SMT) Custom Zen 2 CPU<br>GPU: 12 TFLOPS RDNA 2</td></tr></table></div>'
        d,e=parse_page(h,'https://www.xbox.com/en-US/consoles/xbox-series-x','Xbox Series X','series_x','en-US');self.assertIn('Custom Zen 2',e['raw_specs'][0]['value'])
    def test_uk_real_pdp_explicit_model_relation(self):
        u='https://www.microsoft.com/en-gb/d/product-name/942J774TP9JN';d,e=parse_page(captured(u),u,'1883','series_s','en-GB');self.assertEqual(e['identifiers'],{'hardware_model_number':'1883'});self.assertTrue(e['hardware_complete']);self.assertFalse(e['configuration_fields'])
    def test_recovery_preserves_original_raw_and_rejects_procedure_suffix(self):
        u='https://www.microsoft.com/en-us/d/xbox-elite-wireless-controller-series-2/8rsn7j6375gg';d,e=parse_page(captured(u),u,'8RSN7J6375GG/99WM','elite','en-US');self.assertTrue(any(x.name=='Назначаемые кнопки' for x in d.attributes));self.assertTrue(any(x.name=='Комплектация' for x in d.attributes));self.assertNotIn('Drivers available',d.description);self.assertTrue(any('Drivers available' in x['value'] for x in e['raw_specs']));self.assertTrue(any('suffix withheld' in x['reason'] for x in e['configuration_candidates']))
    def test_hardware_ready_without_optional_manual_and_without_retail_claims(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/'db.sqlite3';jobs.initialize(db)
            with storage._connection(db) as c:
                c.execute('INSERT INTO batches VALUES (?,?,?,?,?)',('x','Xbox','Products','{}',storage._now()));c.execute('INSERT INTO products(batch_id,row_number,name,brand,search_code,alternate_code,category,needs_confirmation,issues_json,original_values_json) VALUES (?,?,?,?,?,?,?,?,?,?)',('x',1,'Xbox Series S','Xbox','1883','','consoles',0,'[]','{}'))
            pid=storage.get_batch(db,'x')['products'][0]['id'];d,e=parse_page(own(model='1883'),PDP,'1883','series_s','en-US');e['manual_status']='Не проверена';e['configuration_scope']='hardware_only';jobs.save_source_document(db,pid,d);card_evidence.save(db,pid,'xbox',e);jobs.resolve_product(db,pid);jobs.set_photo_selection(db,pid,e['exact_photo_assets'],mode='exact');r=xbox_pipeline.card_readiness(db,pid);self.assertEqual(r['verdict'],'export_ready');self.assertFalse(r['configuration_fields']);self.assertIn('manual_unverified',r['advisory_gaps'])

if __name__=='__main__':unittest.main()
