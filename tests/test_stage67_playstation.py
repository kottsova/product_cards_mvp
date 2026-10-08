"""Exact-link discovery, row routing and retail/hardware negative controls."""
import hashlib,json,time,unittest
from pathlib import Path
from product_tool.adapters.playstation import PlayStationAdapter,parse_page,parse_hardware_specs
from product_tool.playstation_discovery import query_variants,identifier_relation,search_kind
from product_tool.playstation_specs import cover_matches
from product_tool.resolution import resolve_attributes
R=Path(__file__).resolve().parents[1]/'reports/playstation_stage66'

class NoSearch:
    trace_callback=None
    def search_provider(self,*args):raise AssertionError('Exact catalogue hit must not launch external search')
    def close(self):pass

class Stage67PlayStation(unittest.TestCase):
    def test_nested_own_box_list_does_not_repeat_whole_kit(self):
        body='<h1>PlayStation 5 Digital Edition 825 GB Fortnite Bundle</h1><script>digitalData.product[0].productInfo = { sku: "11111111-GB" };</script><div class="section-component"><h2>What\'s in the box</h2><ul><li><ul><li>PS5 Digital Console</li><li>DualSense Controller</li><li><ul><li>Fortnite voucher</li><li>USB cable</li></ul></li></ul></li></ul></div>'
        for html in (body,body.replace('section-component','section-wrapper')):
            doc,ev=parse_page(html,'https://direct.playstation.com/en-gb/buy-consoles/fortnite-bundle','11111111-GB','ps5')
            self.assertEqual(ev['configuration_fields']['bundle_contents'],'PS5 Digital Console; DualSense Controller; Fortnite voucher; USB cable')
    def test_matching_cfi_on_other_color_does_not_apply_its_retail_sku(self):
        import tempfile
        from product_tool.adapters.lg_browser_search import BrowserSearchResult
        pdp='https://direct.playstation.com/en-gb/buy-accessories/dualsense-limited-black'
        pages={'https://direct.playstation.com/en-gb/':'<a href="/en-gb/sitemap">Site Map</a>',
               'https://direct.playstation.com/en-gb/sitemap':f'<a href="{pdp}">DualSense</a>',
               pdp:'<h1>DualSense Wireless Controller Midnight Black Limited Edition</h1><script>digitalData.product[0].productInfo = { sku: "11111111-GB" };</script><p>Model Number - CFI-ZCT1W</p><h2>Features</h2><p>Haptic feedback and adaptive triggers.</p>'}
        class Session:
            def get(self,url,**kwargs):return type('Response',(),dict(url=url,status_code=200 if url in pages else 404,text=pages.get(url,''),truncated=False))()
        class Search:
            trace_callback=None
            def search_provider(self,provider,query):return BrowserSearchResult('global',query,'no_candidates',())
            def close(self):pass
        with tempfile.TemporaryDirectory() as tmp:
            a=PlayStationAdapter(fetch_log_path=Path(tmp)/'fetch.json',session=Session(),search_factory=Search)
            a.find_source('CFI-ZCT1W',name='DualSense Wireless Controller White',deadline=time.monotonic()+30)
            e=a.reports['CFI-ZCT1W'];relation=e['sku_cfi_relations'][0]
            self.assertEqual(relation['requested_relation'],'exact_cfi');self.assertFalse(relation['accepted_for_request'])
            self.assertFalse(e.get('retail_sku'));self.assertFalse(e['configuration_fields']);self.assertFalse(e['exact_photo_assets'])
    def test_ps5_compatibility_does_not_make_an_accessory_a_console(self):
        for title in ('Disc Drive for PS5 Digital Edition Consoles', 'Vertical Stand for PS5 Consoles', 'PULSE Explore Wireless Earbuds - PS5', 'DualSense Charging Station - PS5'):
            doc,ev=parse_page('<h1>'+title+'</h1><h2>Features</h2><p>Haptic feedback</p>', 'https://direct.playstation.com/en-gb/buy-accessories/unrelated', 'CFI-1216A', 'ps5')
            self.assertTrue(doc.error);self.assertFalse(doc.attributes);self.assertFalse(ev['exact_photo_assets'])
    def slim(self,code,**kwargs):
        return parse_hardware_specs((R/'CFI-2016A_B_text.txt').read_text(encoding='utf-8'),'https://www.playstation.com/ps5-docs/2000ab/safety.pdf',code,**kwargs)
    def test_slim_disc_and_digital_rows_are_distinct(self):
        facts=[]
        for c,drive in [('CFI-2016A','with_disc'),('CFI-2016B','without_disc')]:
            d,raw,candidates=self.slim(c,linked_codes=['CFI-2016A','CFI-2016B'],drive_relation=drive)
            facts.append({a.name:a.value for a in d.attributes})
            self.assertTrue(all(x.get('hardware_code',c)==c for x in raw))
        self.assertEqual(facts[0]['Высота товара, мм'],'96 мм');self.assertEqual(facts[1]['Высота товара, мм'],'80 мм')
        self.assertEqual(facts[0]['Вес товара'],'Approx. 3.2 kg');self.assertEqual(facts[1]['Вес товара'],'Approx. 2.6 kg')
        self.assertEqual(facts[0]['Оптический привод'],'Ultra HD Blu-ray');self.assertEqual(facts[1]['Оптический привод'],'Без установленного привода')
        self.assertEqual(facts[0]['Объём накопителя'],facts[1]['Объём накопителя'])
    def test_regional_cfi_is_not_covered_by_nearby_pair(self):
        d,raw,candidates=self.slim('CFI-2015A',linked_codes=['CFI-2016A','CFI-2016B'],drive_relation='with_disc')
        self.assertFalse(d.attributes);self.assertTrue(candidates)
    def test_slim_requires_drive_binding_not_input_name(self):
        d,raw,candidates=self.slim('CFI-2016B',linked_codes=['CFI-2016A','CFI-2016B'])
        self.assertFalse(d.attributes);self.assertTrue(candidates)
    def test_ambiguous_column_order_never_confirms_mass_or_dimensions(self):
        t=(R/'CFI-2016A_B_text.txt').read_text(encoding='utf-8').replace('Console with the disc drive','Other hardware column')
        d,raw,c=parse_hardware_specs(t,'https://www.playstation.com/ps5-docs/2000ab/safety.pdf','CFI-2016B',linked_codes=['CFI-2016A','CFI-2016B'],drive_relation='without_disc')
        self.assertFalse(d.attributes);self.assertTrue(c)
    def test_shared_placeholder_cover_requires_exact_link(self):
        self.assertTrue(cover_matches('Safety Guide CFI-20XX','CFI-2015A',{'CFI-2015A','CFI-2015B'}))
        self.assertFalse(cover_matches('Safety Guide CFI-20XX','CFI-2015A',{'CFI-2016A','CFI-2016B'}))
        self.assertFalse(cover_matches('Safety Guide CFI-20XX','CFI-2115A',{'CFI-2115A','CFI-2115B'}))
    def test_component_specs_never_become_console_specs(self):
        d,raw,c=self.slim('CFI-2016B',linked_codes=['CFI-2016A','CFI-2016B'],drive_relation='without_disc')
        self.assertFalse(any('280' in a.value or a.name=='Ёмкость аккумулятора' for a in d.attributes))
    def test_cfi_relations_preserve_drive_region_revision_ec(self):
        self.assertEqual(identifier_relation('CFI-1216A','CFI-1216B'),'same_family_other_drive')
        self.assertEqual(identifier_relation('CFI-2016A','CFI-2015A'),'regional_suffix')
        self.assertEqual(identifier_relation('CFI-2016A','CFI-2116A'),'nearby_revision')
        self.assertNotEqual(identifier_relation('CFI-ZWH2EC','CFI-ZWH2'),'exact_cfi')
    def test_queries_include_exact_normalized_and_variant(self):
        values=query_variants('CFI-2016B','PS5 Slim Digital')
        self.assertIn('CFI-2016B',values);self.assertIn('CFI2016B',values);self.assertIn('PS5 Slim Digital',values)
        self.assertIn('1000050213-GB',query_variants('1000050213-GB','DualSense Midnight Black'))
    def test_new_black_sku_does_not_link_to_old_zct1w(self):
        body=(R/'direct_black.html').read_text(encoding='utf-8');u='https://direct.playstation.com/en-gb/buy-accessories/black'
        d,e=parse_page(body,u,'1000050213-GB','dualsense')
        self.assertEqual(e['sku_cfi_relation']['published_cfi'],['CFI-ZCT2W'])
        d,e=parse_page(body,u,'CFI-ZCT1W','dualsense')
        self.assertTrue(e['hardware_mismatch']);self.assertFalse(e['exact_photo_assets']);self.assertNotEqual(e['identity']['hardware'],'official_hardware_model_code')
    def test_exact_mpn_table_dimensions_are_not_retail_claims(self):
        body=(R/'elite.html').read_text(encoding='utf-8');u='https://www.playstation.com/en-gb/accessories/pulse-elite-wireless-headset/'
        d,e=parse_page(body,u,'CFI-ZWH2EC','elite')
        self.assertEqual(e['identity']['hardware'],'official_hardware_model_code');self.assertEqual(dict(e['hardware_attributes'])['Высота товара, мм'],'251 мм')
        self.assertNotEqual(d.match_level,'full_sku');self.assertFalse(e['configuration_fields']);self.assertTrue(e['photo_scopes'])
        other,oe=parse_page(body,u,'CFI-ZWH2','elite');self.assertFalse(oe.get('hardware_attributes'));self.assertFalse(oe['exact_photo_assets'])
    def test_hardware_specs_remain_independent_of_photos(self):
        d,raw,c=self.slim('CFI-2016B',linked_codes=['CFI-2016A','CFI-2016B'],drive_relation='without_disc')
        self.assertGreaterEqual(len(d.attributes),12);self.assertFalse(d.photos)
        f=dict(source_key='playstation_hardware',normalized_name='product_dimensions__height',normalized_value='80',unit='мм')
        r=resolve_attributes([f],[dict(source_key='playstation_hardware',match_level='hardware_confirmed',error='')])[0]
        self.assertEqual(r.status,'hardware_confirmed_official');self.assertFalse(r.full_sku_confirmed)
    def test_search_classifier_uses_actual_official_hosts(self):
        self.assertEqual(search_kind('https://direct.playstation.com/en-gb/buy-consoles/arbitrary-product'),'product')
        self.assertEqual(search_kind('https://www.playstation.com/en-gb/support/hardware/manuals/'),'support')
        self.assertEqual(search_kind('https://playstation.com.evil.test/en-gb/buy-consoles/ps5'),'unknown')
    def test_retail_sku_without_cfi_cannot_confirm_revision_dimensions(self):
        for name in ('product_dimensions__height','product_weight','максимальная_потребляемая_мощность'):
            f=dict(source_key='playstation',normalized_name=name,normalized_value='100',unit='мм')
            r=resolve_attributes([f],[dict(source_key='playstation',match_level='full_sku',error='')])[0]
            self.assertEqual(r.status,'needs_review');self.assertFalse(r.selected_value)
    def test_hardware_code_cannot_confirm_retail_color_or_bundle(self):
        for name in ('color','комплектация','region'):
            f=dict(source_key='playstation_hardware',normalized_name=name,normalized_value='White',unit='')
            r=resolve_attributes([f],[dict(source_key='playstation_hardware',match_level='hardware_confirmed',error='')])[0]
            self.assertEqual(r.status,'needs_review');self.assertFalse(r.full_sku_confirmed)
    def test_other_color_inside_own_gallery_is_candidate(self):
        body='<h1>DualSense Wireless Controller Midnight Black</h1><script>digitalData.product[0].productInfo = { sku: "99999999-GB" };</script><image-cluster><img src="https://media.direct.playstation.com/is/image/psdglobal/dualsense-white-front" alt="DualSense Wireless Controller White"></image-cluster>'
        d,e=parse_page(body,'https://direct.playstation.com/en-gb/buy-accessories/dualsense-black','99999999-GB','dualsense')
        self.assertFalse(d.photos);self.assertTrue(e['photo_candidates'])
    def test_other_bundle_inside_own_gallery_is_candidate(self):
        body='<h1>PlayStation 5 Digital Edition 825 GB Fortnite Flowering Chaos Bundle</h1><script>digitalData.product[0].productInfo = { sku: "99999999-GB" };</script><image-cluster><img src="https://media.direct.playstation.com/is/image/psdglobal/ps5-ea-fc-26-bundle-packaging" alt="PlayStation 5 EA Sports FC 26 Bundle"></image-cluster>'
        d,e=parse_page(body,'https://direct.playstation.com/en-gb/buy-consoles/fortnite-bundle','99999999-GB','ps5')
        self.assertFalse(d.photos);self.assertTrue(e['photo_candidates'])
    def test_mixed_color_mpn_image_list_needs_variant_evidence(self):
        data={'@type':'Product','name':'PULSE Elite','mpn':'CFI-ZWH2EC','image':['https://gmedia.playstation.com/is/image/SIEPDC/Pulse-Elite-White-front','https://gmedia.playstation.com/is/image/SIEPDC/Pulse-Elite-Midnight-Black-front']}
        d,e=parse_page('<h1>PULSE Elite Wireless Headset</h1><script type="application/ld+json">'+json.dumps(data)+'</script>','https://www.playstation.com/en-gb/accessories/pulse-elite-wireless-headset/','CFI-ZWH2EC','elite')
        self.assertFalse(e['exact_photo_assets']);self.assertTrue(e['photo_candidates'])
    def test_direct_api_candidates_require_declared_get_endpoint(self):
        from product_tool.playstation_discovery import direct_catalog_candidates
        class Adapter:
            calls=[]
            def emit(self,**kwargs):pass
            def fetch(self,u,*args):
                self.calls.append(u)
                body='<div aemEndpoints=\'{"getSearchDataMethod":"GET","getSearchDataUrl":"https://api.direct.playstation.com/commercewebservices/ps-direct-gb/products/search?lang=en_GB"}\'></div>' if '/en-gb/search' in u else json.dumps({'products':[{'code':'99999999-GB','url':'/en-gb/buy-accessories/dualsense-unseen-product'}]})
                return type('Response',(),dict(text=body,url=u))()
        a=Adapter();home=type('Response',(),dict(text='<input data-searchurl="/en-gb/search">',url='https://direct.playstation.com/en-gb/'))()
        result=direct_catalog_candidates(a,home,'99999999-GB','DualSense',time.monotonic()+30)
        self.assertEqual(result,['https://direct.playstation.com/en-gb/buy-accessories/dualsense-unseen-product']);self.assertIn('query=99999999-GB',a.calls[-1])
        b=Adapter();b.calls=[];bad=type('Response',(),dict(text='<input data-searchurl="/en-gb/checkout">',url=home.url))()
        self.assertFalse(direct_catalog_candidates(b,bad,'99999999-GB','DualSense',time.monotonic()+30));self.assertFalse(b.calls)
    def test_autonomous_catalogue_discovery_has_no_known_url_input(self):
        sku='987654321-GB';pdp='https://direct.playstation.com/en-gb/buy-accessories/dualsense-midnight-black-unseen-product'
        pages={
            'https://www.playstation.com/sitemap_index.xml':'<sitemapindex><sitemap><loc>https://www.playstation.com/en-gb/sitemap.xml</loc></sitemap></sitemapindex>',
            'https://www.playstation.com/en-gb/sitemap.xml':'<urlset><url><loc>https://www.playstation.com/en-gb/accessories/dualsense-wireless-controller/</loc></url></urlset>',
            'https://direct.playstation.com/en-gb/':'<a href="/en-gb/sitemap">Site Map</a>',
            'https://direct.playstation.com/en-gb/sitemap':f'<a href="{pdp}">DualSense Midnight Black</a>',
            pdp:'<h1>DualSense Wireless Controller - Midnight Black</h1><script>digitalData.product[0].productInfo = { sku: "'+sku+'" };</script><h2>Features</h2><p>Haptic feedback, adaptive triggers and built-in microphone.</p><div class="section-component"><h2>What\'s in the box</h2><ul><li>DualSense Wireless Controller</li><li>User manual</li></ul></div><image-cluster><img data-src="https://media.direct.playstation.com/is/image/psdglobal/dualsense-midnight-black-own" alt="DualSense Wireless Controller Midnight Black"></image-cluster>'}
        class Session:
            calls=[]
            def get(self,url,**kwargs):
                self.calls.append(url);return type('Response',(),dict(url=url,status_code=200 if url in pages else 404,text=pages.get(url,''),truncated=False))()
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            s=Session();events=[];a=PlayStationAdapter(fetch_log_path=Path(tmp)/'fetch.json',session=s,search_factory=NoSearch,trace_callback=events.append)
            d=a.find_source(sku,name='DualSense Midnight Black',deadline=time.monotonic()+30)
            self.assertEqual(d.url,pdp);self.assertEqual(d.match_level,'full_sku');self.assertTrue(a.reports[sku]['configuration_complete'])
            self.assertLess(s.calls.index('https://www.playstation.com/en-gb/sitemap.xml'),s.calls.index(pdp))
            self.assertTrue(any(e.get('provider')=='official_sitemap' for e in events))
            self.assertTrue(any(e.get('identity_relation')=='exact_order_sku' for e in events))
    def test_frozen_dataset_unchanged(self):
        self.assertEqual(hashlib.sha256((R/'dataset_frozen.json').read_bytes()).hexdigest(),'c2cac5f22132a2061c2ad114b1fa6030188f1ad26ddfc665734d0a75014d1422')
    def test_rerun_cfi_change_does_not_retain_old_revision_facts(self):
        import tempfile
        from product_tool import jobs,storage,card_evidence,worker
        from product_tool.adapters.common import SourceDocument,RawAttribute
        class Adapter:
            extra_documents=[]
            reports={'99999999-GB':dict(identity={'model':'model_confirmed','configuration':'exact_order_sku','hardware':'official_hardware_model_code'},hardware_model='CFI-ZCT2W',configuration_complete=True,manual_status='Не проверена',exact_photo_assets=[])}
            def find_source(self,*args,**kwargs):return SourceDocument('playstation','PlayStation','https://direct.playstation.com/en-gb/buy-accessories/dualsense-black',found_model='DualSense Black',match_level='full_sku',attributes=[RawAttribute('Haptic Feedback','Да'),RawAttribute('Adaptive Triggers','Да'),RawAttribute('Микрофон','Встроенный')])
        class Dealer:
            def find_source(self,*args,**kwargs):return SourceDocument('dns','DNS','',match_level='dealer_url_needed')
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/'batches.sqlite3';jobs.initialize(db)
            with storage._connection(db) as c:
                c.execute('INSERT INTO batches VALUES (?,?,?,?,?)',('rerun','PS rerun','Products','{}',storage._now()))
                c.execute('INSERT INTO products (batch_id,row_number,name,brand,search_code,alternate_code,category,needs_confirmation,issues_json,original_values_json) VALUES (?,?,?,?,?,?,?,?,?,?)',('rerun',1,'DualSense Black','PlayStation','99999999-GB','','controllers',0,'[]','{}'))
            pid=storage.get_batch(db,'rerun')['products'][0]['id']
            jobs.save_source_document(db,pid,SourceDocument('playstation_hardware','Old guide','https://www.playstation.com/old.pdf',found_model='CFI-ZCT1W',match_level='hardware_confirmed',attributes=[RawAttribute('Высота товара, мм','66 мм')]))
            jobs.enqueue(db,pid,[1,2,3,4,6]);worker.run_once(db,playstation_adapter_factory=Adapter,dns_adapter_factory=Dealer)
            self.assertFalse(any(f['source_key']=='playstation_hardware' for f in jobs.get_facts(db,pid)))
            self.assertEqual(card_evidence.load(db,pid,'playstation')['superseded_hardware']['source']['found_model'],'CFI-ZCT1W')

if __name__=='__main__':unittest.main()
