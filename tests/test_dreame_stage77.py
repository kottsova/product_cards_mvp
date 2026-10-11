"""Native capture regression is offline parser evidence, never a live success claim."""
import hashlib,json,tempfile,time,unittest,sqlite3
from pathlib import Path
from datetime import datetime,timezone,timedelta
from unittest.mock import Mock,patch
from bs4 import BeautifulSoup
from product_tool.dreame_page import parse_page
from product_tool.adapters.dreame import DreameAdapter
from product_tool.adapters import access_stop,policy_fetch
from product_tool import jobs,card_evidence,xiaomi_pipeline
R=Path(__file__).resolve().parents[1]/'reports/dreame_stage77'
HTML=R/'h14_control/captures/d06ce92bdda83f5860710a26e9976d2ccfa47711b206316b3b0febe6b04d8c10.html'
URL='https://global.dreametech.com/products/h14-pro'
def parsed(html=None,name='Dreame H14 Pro [region=RU;color=Supplier Blue]'):
 return parse_page(html or HTML.read_text(encoding='utf8'),URL,'SUPPLIER-77',name,'Вертикальные моющие пылесосы')
class Stage77Tests(unittest.TestCase):
 def test_native_capture_hash_and_no_product_jsonld(self):
  self.assertEqual(hashlib.sha256(HTML.read_bytes()).hexdigest(),'a33dd6a6f59eb1822ac09c1478b0aecf6cf71525a051dc7e71898844631806c3')
  s=BeautifulSoup(HTML.read_text(encoding='utf8'),'html.parser');self.assertIsNotNone(s.select_one('.common-spec-content'));self.assertFalse(s.select('script[type="application/ld+json"]'))
 def test_native_specifications_and_provenance(self):
  d,e=parsed();self.assertEqual(len(d.attributes),13);self.assertTrue(all(x.section=='Устройство' for x in d.attributes));self.assertTrue(all(x['section']=='Specifications' for x in e['original_raw_specs']));self.assertTrue(all(x['source_section']=='Specifications' for x in e['accepted_specs']))
  values={x.name:x.value for x in d.attributes};self.assertEqual(values['Battery Capacity'],'6 x 5,000mAh');self.assertEqual(values['Weight'],'12.57 lbs (5.7kg)');self.assertEqual(values['Maximum Runtime'],'40min')
 def test_native_continuation_preserves_two_tank_states(self):
  d,e=parsed();v={x.name:x.value for x in d.attributes};self.assertEqual(v['Used Water Tank — Standing'],'650mL');self.assertEqual(v['Used Water Tank — Lie-Flat'],'450mL');self.assertIn('Lie-Flat: 450mL',next(x['value'] for x in e['original_raw_specs'] if x['name']=='Used Water Tank'))
 def test_marketing_headings_not_technical_specs(self):
  d,e=parsed();self.assertTrue(any('18kPa' in x for x in e['native_feature_headings']));self.assertFalse(any('18kPa' in x.value or '60°C' in x.value for x in d.attributes));self.assertEqual(d.description,'')
 def test_metadata_gallery_model_first(self):
  d,e=parsed();g=[x for x in e['model_gallery_candidates'] if x['role']=='model_metadata_gallery'];self.assertEqual(len(g),3);self.assertTrue(all(x['model_relation']=='model_confirmed' and x['supplier_color_relation']=='unproven' for x in g));self.assertFalse(any(x['accepted'] for x in g));self.assertEqual(e['input_configuration']['supplier_part_number'],'SUPPLIER-77')
 def test_shopify_resize_aliases_dedup_without_merging_crop_or_revision(self):
  from product_tool.dreame_page import media_asset_key
  a='https://www.dreametech.com/cdn/shop/files/render.jpg?v=10&width=1024'
  b='https://www.dreametech.com/cdn/shop/files/render_1200x1200.jpg?v=10'
  self.assertEqual(media_asset_key(a),media_asset_key(b))
  for other in [b.replace('v=10','v=11'),b+'&crop=center',b.replace('render_','different_')]:self.assertNotEqual(media_asset_key(a),media_asset_key(other))
 def test_native_us_gallery_retains_alias_provenance_but_one_render(self):
  r=R/'stable_live/first/8';v=json.loads((r/'result.json').read_text(encoding='utf8'));e=v['evidence'];c=next(x for x in e['captures'] if x['url']==e['pdp_url'])
  d,e=parse_page((r/'captures'/c['file']).read_text(encoding='utf8'),c['url'],v['input']['article'],v['input']['name'],v['input']['category'])
  renders=[x for x in d.photo_candidates if '/Z30_e8f' in x.url];self.assertEqual(len(renders),1)
  self.assertTrue(any('/Z30_e8f' in x['url'] and not x['accepted'] for x in e['gallery_asset_aliases']))
  self.assertEqual(len({x.asset_key for x in d.photo_candidates}),len(d.photo_candidates))
 def test_metadata_other_model_or_url_not_gallery(self):
  for fragment,replacement in [('content="H14 Pro"','content="H14 Pro Heat"'),('content="https://global.dreametech.com/products/h14-pro"','content="https://global.dreametech.com/products/other"')]:
   d,e=parsed(HTML.read_text(encoding='utf8').replace(fragment,replacement));self.assertFalse(any(x['role']=='model_metadata_gallery' for x in e['model_gallery_candidates']))
 def test_package_accessories_and_placeholders_not_confirmed(self):
  d,e=parsed();accessory=[x for x in e['model_gallery_candidates'] if x['role']=='accessory_or_bundle'];self.assertGreater(len(accessory),3);self.assertTrue(all(x['model_relation']=='unproven' for x in accessory));self.assertFalse(any('no-image' in x.url for x in d.photo_candidates));self.assertTrue(any(x['role']=='placeholder' for x in e['native_media_inventory']))
 def test_mismatch_primary_model_blocks_specs_and_gallery(self):
  d,e=parsed(name='Dreame H13 Pro');self.assertFalse(d.attributes);self.assertFalse(d.photo_candidates)
 def test_host_stop_before_browser_and_catalog_cache(self):
  with tempfile.TemporaryDirectory() as tmp:
   log=Path(tmp)/'log.json';policy_fetch.append_log_entry(log,access_stop.stop_event('global.dreametech.com',access_stop.RATE_LIMIT,source_session='test'))
   b=Mock();b.status=None;b.signal="";b.events=[];a=DreameAdapter(browser_session=b,fetch_log_path=log);a.deadline=time.monotonic()+30;a.catalog_cache[URL]=('cached',URL)
   self.assertEqual(a.fetch(URL,cache=True),'');b.start.assert_not_called();b.call.assert_not_called();self.assertEqual(a.access_issues[0]['status'],'host_stopped');self.assertIn('global.dreametech.com',access_stop.active_stops(policy_fetch.read_log(log)))
 def test_ttl_host_scope_no_manual_reset(self):
  now=datetime.now(timezone.utc);e=access_stop.stop_event('global.dreametech.com',access_stop.RATE_LIMIT,at=now)
  self.assertIn('global.dreametech.com',access_stop.active_stops([e],now=now+timedelta(minutes=59)));self.assertNotIn('www.dreametech.com',access_stop.active_stops([e],now=now));self.assertFalse(access_stop.active_stops([e],now=now+timedelta(hours=1,seconds=1)));self.assertEqual(e['reason'],access_stop.RATE_LIMIT)
 def test_fresh_429_prevents_next_transport_attempt(self):
  from product_tool.census.browser_runtime import BrowserFailure
  with tempfile.TemporaryDirectory() as tmp:
   b=Mock();b.status=None;b.signal="";b.events=[];b.call.side_effect=BrowserFailure('rate_limited',{'navigations':1});a=DreameAdapter(browser_session=b,fetch_log_path=Path(tmp)/'log.json');a.deadline=time.monotonic()+30
   self.assertEqual(a.fetch(URL),'');self.assertTrue(a.new_access_stop);self.assertEqual(a.fetch('https://www.dreametech.com/'),'');self.assertEqual(b.call.call_count,1)
 def test_access_readiness_reason_and_optional_manual(self):
  with tempfile.TemporaryDirectory() as tmp:
   db=Path(tmp)/'live.sqlite3';jobs.initialize(db)
   with sqlite3.connect(db) as c:
    c.execute("INSERT INTO batches VALUES ('test','test.xlsx','Products','{}','2026-10-11')");c.execute("INSERT INTO products (id,batch_id,row_number,name,brand,search_code,alternate_code,category,needs_confirmation,issues_json,original_values_json) VALUES (1,'test',2,'Dreame H14 Pro','Dreame','H14 Pro','','',0,'[]','[]')")
   c.close()
   card_evidence.save(db,1,'dreame',{'identity':{'model_relation':'unproven'},'access_issues':[{'host':'global.dreametech.com','status':'host_stopped'}],'manual_status':'Не проверена'})
   with patch.object(jobs,'result_counts',return_value={'conflicts':0}),patch.object(jobs,'get_resolved',return_value=[]),patch.object(jobs,'get_photo_candidates',return_value=[]):
    r=xiaomi_pipeline.card_readiness(db,1,family='dreame');self.assertEqual(r['blocking_gaps'],['official_access_limited']);self.assertEqual(r['advisory_gaps'],['manual_unverified'])

 def native_model(self,ident):
  r=R/'batch_live/first'/str(ident);v=json.loads((r/'result.json').read_text(encoding='utf8'));c=next(x for x in v['evidence']['captures'] if '/products/' in x['url']);return parse_page((r/'captures'/c['file']).read_text(encoding='utf8'),c['url'],v['input']['article'],v['input']['name'],v['input']['category'])
 def test_native_x50_explicit_component_weights(self):
  d,e=self.native_model(4);self.assertEqual(len(d.attributes),4);self.assertEqual([(x.value,x.section) for x in d.attributes if x.name=='Weight'],[('4.53kg','Робот'),('9.09kg','База / станция')]);self.assertEqual(e['input_configuration']['bundle'],'Complete');self.assertIsNone(e['identity']['retail_sku'])
 def test_native_h15_runtime_and_tank_states(self):
  d,e=self.native_model(7);v={x.name:x.value for x in d.attributes};self.assertEqual(v['Maximum Runtime — Quiet Mode'],'72min (Quiet Mode)');self.assertEqual(v['Maximum Runtime — Hot Water Mode'],'20min (Hot Water Mode)');self.assertEqual(v['Used Water Tank — Standing'],'650ml');self.assertEqual(v['Used Water Tank — Lie-Flat'],'400ml')
 def test_native_l60_duplicate_mobile_and_ambiguous_tank(self):
  d,e=self.native_model(1);self.assertEqual(sum(x.name=='Obstacle Crossing Height' for x in d.attributes),1);self.assertEqual(sum(x.name=='Robot Vacuum Dimensions' for x in d.attributes),1);self.assertTrue(any(x['duplicate_presentation'] for x in e['accepted_specs']));self.assertTrue(any('Tank Capacity' in x['name'] for x in e['rejected_specs']));self.assertFalse(any(x.name=='Clean/Waste Water Tank Capacity' for x in d.attributes))
 def test_native_h12_slogan_identity_and_handheld_runtime(self):
  d,e=self.native_model(9);self.assertEqual(d.match_level,'model_confirmed');v={x.name:x for x in d.attributes};self.assertEqual(v['Maximum Runtime — Wet and Dry Vacuum'].section,'Устройство');self.assertEqual(v['Maximum Runtime — Handheld Vacuum'].section,'Ручной пылесос')
 def test_native_x40_empty_h1_and_hidden_station_table(self):
  d,e=self.native_model(10);self.assertEqual(d.match_level,'model_confirmed');self.assertEqual(len(d.attributes),19);v=[x for x in d.attributes if x.name=='Rated Power'];self.assertEqual([(x.value,x.section) for x in v],[('1,000W','База / станция')]);self.assertTrue(any(x.name=='Dust Bag Capacity' and x.section=='База / станция' for x in d.attributes));self.assertFalse(any('purchased separately' in x.value for x in d.attributes));self.assertTrue(any('Optional accessory' in x['reason'] for x in e['rejected_specs']))
 def test_native_z30_grouped_rpm_matches_raw_without_decimal_regression(self):
  from product_tool.normalization import normalize_value
  r=R/'stable_live/first/8';v=json.loads((r/'result.json').read_text(encoding='utf8'));e=v['evidence'];c=next(x for x in e['captures'] if x['url']==e['pdp_url'])
  d,e=parse_page((r/'captures'/c['file']).read_text(encoding='utf8'),c['url'],v['input']['article'],v['input']['name'],v['input']['category'])
  raw=next(x for x in d.attributes if x.name=='Motor Speed');self.assertEqual(raw.value,'150,000 RPM');self.assertEqual(normalize_value(raw.name,raw.value),('150000','rpm'))
  for value,expected in [('1,500 RPM','1500'),('1,234,567 RPM','1234567'),('1,5 RPM','1.5'),('0,500 RPM','0.5'),('150.000 RPM','150')]:self.assertEqual(normalize_value('Motor Speed',value),(expected,'rpm'))
  self.assertEqual(normalize_value('Weight','1,500 kg'),('1.5','kg'))
 def test_native_z30_slim_h1_overrides_matching_metadata(self):
  d,e=self.native_model(8);self.assertEqual(e['identity']['model_relation'],'unproven');self.assertFalse(d.attributes);self.assertFalse(d.photo_candidates)

 def test_fresh_429_worker_skips_manual_and_dealer_requests(self):
  from product_tool import worker
  from product_tool.census.browser_runtime import BrowserFailure
  with tempfile.TemporaryDirectory() as tmp:
   db=Path(tmp)/'live.sqlite3';jobs.initialize(db)
   with sqlite3.connect(db) as c:
    c.execute("INSERT INTO batches VALUES ('test','test.xlsx','Products','{}','2026-10-11')");c.execute("INSERT INTO products (id,batch_id,row_number,name,brand,search_code,alternate_code,category,needs_confirmation,issues_json,original_values_json) VALUES (1,'test',2,'Dreame H14 Pro','Dreame','H14 Pro','','',0,'[]','[]')")
   c.close();b=Mock();b.status=None;b.signal="";b.events=[];b.call.side_effect=BrowserFailure('rate_limited',{'navigations':1});a=DreameAdapter(browser_session=b,fetch_log_path=Path(tmp)/'log.json');jobs.enqueue(db,1,[1,3,4,6])
   with patch('product_tool.xiaomi_pipeline.DnsAdapter') as dns:
    worker.run_once(db,dreame_adapter_factory=lambda:a);dns.assert_not_called()
   self.assertEqual(b.call.call_count,1);self.assertEqual(card_evidence.load(db,1,'dreame')['manual_status'],'Не проверена');self.assertEqual(xiaomi_pipeline.card_readiness(db,1,family='dreame')['blocking_gaps'],['official_access_limited'])

 def test_native_guide_generation_cover_and_ru_operations(self):
  import pymupdf
  from product_tool.adapters.dreame import manual_assessment
  r=R/'qualified_live/first/2';m=json.loads((r/'result.json').read_text(encoding='utf8'))['evidence']['manuals'][0]
  with pymupdf.open(r/'captures'/m['file']) as pdf:pages=[p.get_text() for p in pdf]
  check,_=manual_assessment(pages,['Dreame L10s Pro Gen 2','L10s Pro Gen 2']);self.assertTrue(check['accepted']);self.assertIn('ru',check['guide_languages']['present']);self.assertFalse(manual_assessment(pages,['Dreame L10s Pro Gen 3'])[0]['accepted']);self.assertFalse(manual_assessment(pages,['Dreame L10s Pro'])[0]['accepted'])
 def test_native_z30_guide_languages_include_operations(self):
  import pymupdf
  from product_tool.adapters.dreame import manual_assessment
  r=R/'qualified_live/first/8';m=json.loads((r/'result.json').read_text(encoding='utf8'))['evidence']['manuals'][0]
  with pymupdf.open(r/'captures'/m['file']) as pdf:pages=[p.get_text() for p in pdf]
  check,_=manual_assessment(pages,['Dreame Z30','Z30']);self.assertTrue(check['accepted']);self.assertIn('en',check['guide_languages']['present']);self.assertIn('ru',check['guide_languages']['present'])
 def test_ru_safety_only_cannot_supply_guide_language(self):
  from product_tool.adapters.dreame import manual_assessment
  pages=['Dreame Audit R1\nUser Manual','How to Use\n'+('the device and the user can press connect install clean charging before use. '*60),'Информация по технике безопасности\n'+('Не подключайте к сети и не нажмите при установке и зарядке для очистки устройства. '*70)]
  check,_=manual_assessment(pages,['Dreame Audit R1']);self.assertTrue(check['accepted']);self.assertIn('en',check['guide_languages']['present']);self.assertNotIn('ru',check['guide_languages']['present'])

 def test_image_429_shared_log_stops_followups(self):
  from product_tool import worker
  with tempfile.TemporaryDirectory() as tmp:
   db=Path(tmp)/'live.sqlite3';jobs.initialize(db)
   with sqlite3.connect(db) as c:
    c.execute("INSERT INTO batches VALUES ('test','test.xlsx','Products','{}','2026-10-11')");c.execute("INSERT INTO products (id,batch_id,row_number,name,brand,search_code,alternate_code,category,needs_confirmation,issues_json,original_values_json) VALUES (1,'test',2,'Dreame H14 Pro','Dreame','H14 Pro','','',0,'[]','[]')")
   c.close();doc,ev=parsed(name='Dreame H14 Pro');a=DreameAdapter(browser_session=Mock(),fetch_log_path=Path(tmp)/'shared.json');a.find_source=Mock(return_value=doc);a.reports={'H14 PRO':ev}
   def denial(url,source,log,**kw):
    self.assertEqual(log,a.log);policy_fetch.append_log_entry(log,access_stop.stop_event('global.dreametech.com',access_stop.RATE_LIMIT,source_session='test'));raise ValueError('429 policy stop')
   jobs.enqueue(db,1,[1,3,4])
   with patch('product_tool.photo_metadata.inspect_saved_photo',side_effect=denial) as inspect,patch('product_tool.xiaomi_pipeline.DnsAdapter') as dns:
    worker.run_once(db,dreame_adapter_factory=lambda:a);self.assertEqual(inspect.call_count,1);dns.assert_not_called()
   self.assertTrue(a.new_access_stop);self.assertFalse(card_evidence.load(db,1,'dreame')['model_gallery_assets']);self.assertIn('global.dreametech.com',access_stop.active_stops(policy_fetch.read_log(a.log)))

 def test_manual_429_prevents_first_gallery_request(self):
  from product_tool import worker
  with tempfile.TemporaryDirectory() as tmp:
   db=Path(tmp)/'live.sqlite3';jobs.initialize(db)
   with sqlite3.connect(db) as c:
    c.execute("INSERT INTO batches VALUES ('test','test.xlsx','Products','{}','2026-10-11')");c.execute("INSERT INTO products (id,batch_id,row_number,name,brand,search_code,alternate_code,category,needs_confirmation,issues_json,original_values_json) VALUES (1,'test',2,'Dreame H14 Pro','Dreame','H14 Pro','','',0,'[]','[]')")
   c.close();doc,ev=parsed(name='Dreame H14 Pro');a=DreameAdapter(browser_session=Mock(),fetch_log_path=Path(tmp)/'shared.json');a.find_source=Mock(return_value=doc);a.reports={'H14 PRO':ev}
   def manual(*args):
    policy_fetch.append_log_entry(a.log,access_stop.stop_event('cdn.shopify.com',access_stop.RATE_LIMIT,source_session='test'));return []
   a.find_documents=Mock(side_effect=manual);jobs.enqueue(db,1,[1,3,4,6])
   with patch('product_tool.photo_metadata.inspect_saved_photo') as inspect,patch('product_tool.xiaomi_pipeline.DnsAdapter') as dns:
    worker.run_once(db,dreame_adapter_factory=lambda:a);inspect.assert_not_called();dns.assert_not_called()
   self.assertTrue(a.new_access_stop);self.assertFalse(card_evidence.load(db,1,'dreame')['model_gallery_assets'])

 def test_received_200_dom_recovered_without_navigation_retry(self):
  from product_tool.census.browser_runtime import BrowserFailure
  with tempfile.TemporaryDirectory() as tmp:
   b=Mock();b.status=200;b.signal='';b.events=[{'status':200,'main_document':True}]
   def call(command,**kw):
    if command=='goto':raise BrowserFailure('render_timeout',{'navigations':1})
    return {'html':HTML.read_text(encoding='utf8'),'url':URL,'status_code':200,'session_id':'fixture-session','counts':{},'response_events':b.events}
   b.call.side_effect=call;events=[];a=DreameAdapter(browser_session=b,fetch_log_path=Path(tmp)/'log.json',trace_callback=events.append);a.deadline=time.monotonic()+30;a.proofs=[]
   result=a.fetch(URL);self.assertTrue(result);self.assertEqual([x.args[0] for x in b.call.call_args_list],['goto','document_snapshot']);self.assertFalse(a.access_issues);self.assertTrue(any(x.get('navigation_warning') for x in events));self.assertEqual(parsed(result[0])[0].match_level,'model_confirmed')
 def test_timeout_without_ordinary_main_200_not_recovered(self):
  from product_tool.census.browser_runtime import BrowserFailure
  for status,signal in [(None,''),(403,'http_denied'),(200,'rate_limited')]:
   with tempfile.TemporaryDirectory() as tmp:
    b=Mock();b.status=status;b.signal=signal;b.events=[];b.call.side_effect=BrowserFailure('render_timeout',{'navigations':1});a=DreameAdapter(browser_session=b,fetch_log_path=Path(tmp)/'log.json');a.deadline=time.monotonic()+30
    self.assertFalse(a.fetch(URL));self.assertEqual(b.call.call_count,1);self.assertTrue(a.access_issues)
 def test_technical_refresh_retains_verified_data_without_live_success(self):
  from product_tool import worker
  with tempfile.TemporaryDirectory() as tmp:
   db=Path(tmp)/'live.sqlite3';jobs.initialize(db)
   with sqlite3.connect(db) as c:
    c.execute("INSERT INTO batches VALUES ('test','test.xlsx','Products','{}','2026-10-11')");c.execute("INSERT INTO products (id,batch_id,row_number,name,brand,search_code,alternate_code,category,needs_confirmation,issues_json,original_values_json) VALUES (1,'test',2,'Dreame H14 Pro','Dreame','H14 Pro','','',0,'[]','[]')")
   c.close();doc,ev=parsed(name='Dreame H14 Pro');a=DreameAdapter(fetch_log_path=Path(tmp)/'shared.json');a.find_source=Mock(return_value=doc);a.reports={'H14 PRO':ev}
   metrics={x['url']:x for x in json.loads((R/'h14_final_control/result.json').read_text(encoding='utf8'))['evidence']['image_measurements'] if 'sha256' in x}
   def measure(url,*args,**kw):
    if url not in metrics:raise ValueError('Small render rejected by existing dimensions policy')
    return {k:metrics[url][k] for k in ('width','height','size_bytes','format','content_type','effective_content_type','sha256')}
   jobs.enqueue(db,1,[1,3,4])
   with patch('product_tool.photo_metadata.inspect_saved_photo',side_effect=measure):worker.run_once(db,dreame_adapter_factory=lambda:a)
   from product_tool.adapters.common import ProductDocument
   jobs.save_documents(db,1,'dreame_model',[ProductDocument('Offline fixture User Guide','Английский','PDF','1000','https://cdn.shopify.com/s/files/fixture/guide.pdf',URL,'H14 Pro','H14 Pro',URL)])
   before=(jobs.get_source_pages(db,1),jobs.get_facts(db,1),jobs.get_photo_candidates(db,1),jobs.get_documents(db,1));self.assertEqual(xiaomi_pipeline.card_readiness(db,1,family='dreame')['verdict'],'export_ready')
   failed,attempt=parse_page('','', 'H14 Pro','Dreame H14 Pro');attempt['access_issues']=[{'host':'www.dreametech.com','status':'render_timeout'}];a.find_source=Mock(return_value=failed);a.reports={'H14 PRO':attempt};jobs.enqueue(db,1,[1,3,4,6])
   with patch('product_tool.photo_metadata.inspect_saved_photo') as inspect,patch('product_tool.xiaomi_pipeline.DnsAdapter') as dns:
    worker.run_once(db,dreame_adapter_factory=lambda:a);inspect.assert_not_called();dns.assert_not_called()
   self.assertEqual(before,(jobs.get_source_pages(db,1),jobs.get_facts(db,1),jobs.get_photo_candidates(db,1),jobs.get_documents(db,1)));kept=card_evidence.load(db,1,'dreame');self.assertFalse(kept['live_success']);self.assertEqual(kept['observation'],'retained_previous_evidence');self.assertTrue(kept['last_live_attempt']['access_issues']);self.assertEqual(xiaomi_pipeline.card_readiness(db,1,family='dreame')['verdict'],'export_ready');self.assertIn('refresh_access_limited',xiaomi_pipeline.card_readiness(db,1,family='dreame')['advisory_gaps']);self.assertEqual(jobs.list_jobs(db,1)[0]['status'],'needs_review')
