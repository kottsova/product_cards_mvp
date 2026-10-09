"""Shared grid recovery and source-scoped SSR/session negative controls."""
import json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock
from product_tool.adapters.structured_page import extract_dom_spec_table
from product_tool.razer_page import parse_page
from product_tool.razer_store import option_equal
from product_tool.census.public_browser import PublicBrowserSession
from product_tool.census.browser_runtime import BrowserFailure
from product_tool.adapters import policy_fetch,access_stop
from product_tool.resolution import resolve_attributes
URL='https://www.razer.com/gaming-keyboards/example'

def node(code='RZ03-99990100-R3U1',color='Black',layout='US Layout',switch='Orange',base='Razer Example'):
 return {'code':code,'baseProductName':base,'name':base+' - '+color,'url':'/gaming-keyboards/example/'+code,'variantOptions':[{'variantOptionQualifiers':[{'qualifier':'color','value':color},{'qualifier':'keyboard-layout','value':layout}]}], 'classifications':[{'features':[{'name':k,'featureValues':[{'value':v}]} for k,v in [('Layout',layout),('Switch Type',switch),('Connectivity','USB'),('Weight','100 g'),('Color / Design',color)]]}],'images':[{'format':'product','imageType':'PRIMARY','url':'https://assets2.razerzone.com/example-'+color.lower()+'.png'}]}
def html(nodes,extra=''):
 return '<h1>Razer Example</h1><script id="ng-state" type="application/json">'+json.dumps({'razerProductMarketingData':{'variants':nodes}})+'</script>'+extra

class GridTests(unittest.TestCase):
 def test_continuation_is_not_heading(self):
  f=extract_dom_spec_table('<table><tr><th rowspan="3">Headphones</th><td>Frequency: 10 Hz</td></tr><tr><td>Impedance: 32 Ohm</td></tr><tr><td>Driver: 50 mm</td></tr><tr><th>Battery</th><td>70 hours</td></tr></table>',URL)
  self.assertEqual([(x.name,x.value,x.section) for x in f],[('Headphones','Frequency: 10 Hz',''),('Headphones','Impedance: 32 Ohm',''),('Headphones','Driver: 50 mm',''),('Battery','70 hours','')])
 def test_colspan_value_and_heading(self):
  f=extract_dom_spec_table('<table><tr><th colspan="3">Technical</th></tr><tr><th>Ports</th><td colspan="2">USB</td></tr></table>',URL);self.assertEqual([(x.name,x.value,x.section) for x in f],[('Ports','USB','Technical')])
 def test_span_never_leaks_between_tables(self):
  f=extract_dom_spec_table('<table><tr><th rowspan="9">A</th><td>B</td></tr></table><table><tr><th>Header</th></tr><tr><th>C</th><td>D</td></tr></table>',URL);self.assertEqual([(x.name,x.value) for x in f],[('A','B'),('C','D')]);self.assertEqual(f[-1].section,'Header')
 def test_malformed_spans_bounded(self):
  f=extract_dom_spec_table('<table><tr><th rowspan="nonsense">A</th><td colspan="-1">B</td></tr></table>',URL);self.assertEqual(len(f),1)
 def test_headphone_and_mic_frequency_do_not_conflict(self):
  raw='<h1>Razer Example | RZ04-9999 Support &amp; FAQs</h1><div id="at-a-glance"><table><tr><th rowspan="2">Headphones</th><td>Frequency response: 12 Hz — 28 kHz</td></tr><tr><td>Drivers: 50 mm</td></tr><tr><th>Microphone</th><td>Frequency response: 100 Hz — 10 kHz</td></tr></table></div>'
  d,e=parse_page(raw,'https://mysupport.razer.com/app/answers/detail/a_id/1','RZ04-9999','Razer Example','Гарнитуры');self.assertEqual(len(d.attributes),3);self.assertNotEqual(d.attributes[0].name,d.attributes[-1].name);self.assertEqual(len(e['raw_specs']),len(e['accepted_specs'])+len(e['rejected_specs']))

class StoreTests(unittest.TestCase):
 def parse(self,nodes,name='Razer Example [color=White; layout=US; switch=Orange]',extra=''):
  return parse_page(html(nodes,extra),URL,'RZ03-9999',name,'Клавиатуры')
 def test_requested_options_without_full_sku(self):
  d,e=self.parse([node(color='Black'),node(code='RZ03-99990200-R3U1',color='White')]);self.assertTrue(e['identity']['model_confirmed']);self.assertEqual(e['identity']['configuration_relation'],'configuration_confirmed');self.assertFalse(e['identity']['exact_sku']);self.assertEqual(d.match_level,'configuration_confirmed');self.assertEqual(len(e['exact_photo_assets']),1);self.assertIn('white',next(x['url'] for x in e['photos'] if x['verified']))
 def test_wrong_layout_image_candidate(self):
  d,e=self.parse([node(layout='UK Layout',color='White')]);self.assertFalse(e['exact_photo_assets']);self.assertEqual(e['identity']['configuration_relation'],'unproven')
 def test_stronger_ssr_image_proof_promotes_existing_candidate_without_duplicate(self):
  n=node(color='White');image=n['images'][0]['url'];extra='<script type="application/ld+json">'+json.dumps({'@type':'Product','name':'Razer Example','image':image})+'</script>'
  d,e=self.parse([n],extra=extra);self.assertEqual(len(d.photo_candidates),1);self.assertEqual(len(e['photos']),1);self.assertEqual(len(e['exact_photo_assets']),1)
 def test_switch_unproven_image_remains_candidate(self):
  d,e=self.parse([node(color='White',switch='Unknown')]);self.assertFalse(e['exact_photo_assets'])
 def test_switch_not_inferred_from_tactile(self):
  d,e=self.parse([node(color='White',switch='Mechanical Tactile')]);self.assertEqual(e['identity']['configuration_relation'],'unproven')
 def test_swappable_switch_demo_not_default(self):
  d,e=self.parse([node(color='White',switch='Mechanical Tactile')],extra='<h2>Razer Orange Mechanical Switches</h2><p>Sound test alternative</p>');self.assertEqual(e['identity']['configuration_relation'],'unproven')
 def test_other_hardware_never_matches(self):
  d,e=self.parse([node(code='RZ03-88880100-R3U1',color='White')]);self.assertFalse(e['identity']['model_confirmed']);self.assertFalse(d.attributes)
 def test_neighbor_model_never_matches(self):
  d,e=self.parse([node(base='Razer Example Pro',color='White')]);self.assertFalse(e['identity']['model_confirmed'])
 def test_no_default_variant_weight(self):
  n=node(code='RZ03-99990200-R3U1',color='White');n['classifications'][0]['features'][3]['featureValues'][0]['value']='110 g'
  d,e=self.parse([node(),n],name='Razer Example');self.assertFalse(any(x.name=='Вес' for x in d.attributes));self.assertTrue(any(x['raw_label']=='Weight' for x in e['rejected_specs']))
 def test_generation_needs_support_relation(self):
  raw=html([node(base='Razer Example')]);name='Razer Example (2023)'
  d,e=parse_page(raw,URL,'RZ03-9999',name);self.assertFalse(e['identity']['model_confirmed'])
  proof={'model_confirmed':True,'model_code':'RZ03-99990'};d,e=parse_page(raw,URL,'RZ03-9999',name,model_evidence=proof);self.assertTrue(e['identity']['model_confirmed'])
  d,e=parse_page(raw,URL,'RZ03-9999',name,model_evidence={**proof,'model_code':'RZ03-8888'});self.assertFalse(e['identity']['model_confirmed'])
 def test_configuration_source_is_not_full_sku(self):
  r=resolve_attributes([{'normalized_name':'Color','normalized_value':'White','unit':'','source_key':'razer_configuration'}],[{'source_key':'razer_configuration','match_level':'configuration_confirmed','error':''}])[0];self.assertEqual(r.status,'configuration_confirmed_official');self.assertFalse(r.full_sku_confirmed)
 def test_laptop_values_not_substrings(self):
  self.assertTrue(option_equal('GPU','RTX 5080','GeForce RTX 5080 (16 GB GDDR7 VRAM)'));self.assertFalse(option_equal('GPU','RTX 5080','GeForce RTX 5080 Ti'));self.assertFalse(option_equal('RAM','32 GB','64 GB'));self.assertFalse(option_equal('storage','1 TB','2 TB SSD'))
 def test_footer_recommendations_not_product_evidence(self):
  raw='<script id="ng-state" type="application/json">'+json.dumps({'recommendations':{'variants':[node(color='White')]}})+'</script>';d,e=parse_page(raw,URL,'RZ03-9999','Razer Example');self.assertFalse(e['identity']['model_confirmed'])
 def test_support_diagram_not_gallery(self):
  raw='<h1>Razer Example | RZ04-9999 Support &amp; FAQs</h1><div id="at-a-glance"><p><img src="https://dl.razerzone.com/render.png"></p><h2>Device Layout</h2><img alt="Device Layout" src="https://dl.razerzone.com/diagram.png"></div>'
  d,e=parse_page(raw,'https://mysupport.razer.com/app/answers/detail/a_id/1','RZ04-9999','Razer Example');self.assertEqual(len(e['exact_photo_assets']),1);self.assertEqual(e['photos'][0]['relation'],'model_render');self.assertFalse(e['photos'][0]['color_verified']);self.assertEqual(e['photos'][1]['role'],'technical_diagram')
 def test_support_render_does_not_prove_requested_color(self):
  raw='<h1>Razer Example | RZ04-9999 Support &amp; FAQs</h1><div id="at-a-glance"><p><img src="https://dl.razerzone.com/render.png"></p></div>';d,e=parse_page(raw,'https://mysupport.razer.com/app/answers/detail/a_id/1','RZ04-9999','Razer Example [color=Quartz]');self.assertFalse(e['exact_photo_assets'])

class SessionTests(unittest.TestCase):
 def make(self,tmp):
  d=PublicBrowserSession(allowed_hosts=('razer.com','razerzone.com'),fetch_log_path=Path(tmp)/'fetch.json',pause=lambda _:None);d.page=Mock();d.page.url='https://mysupport.razer.com/app/answers/list/kw/example';d.page.content.return_value='<h1>Ordinary official search</h1>';d.status=200;return d
 def response(self,url,status,main):
  r=Mock();r.url=url;r.status=status;r.request.is_navigation_request.return_value=main;return r
 def test_positive_dom_does_not_create_cooldown(self):
  with tempfile.TemporaryDirectory() as tmp:
   d=self.make(tmp);self.assertEqual(d.snapshot()['status_code'],200);self.assertFalse(access_stop.active_stops(policy_fetch.read_log(d.log)))
 def test_main_403_recorded_as_denial_not_captcha(self):
  with tempfile.TemporaryDirectory() as tmp:
   d=self.make(tmp);r=self.response(d.page.url,403,True);r.request.frame=d.page.main_frame;d.response(r)
   with self.assertRaisesRegex(BrowserFailure,'http_denied'):d.snapshot()
   self.assertEqual(access_stop.active_stops(policy_fetch.read_log(d.log))['mysupport.razer.com'][0]['reason'],access_stop.HTTP_DENIED)
 def test_ancillary_403_not_document_host_stop(self):
  with tempfile.TemporaryDirectory() as tmp:
   d=self.make(tmp);d.response(self.response('https://assets2.razerzone.com/widget.js',403,False));self.assertEqual(d.snapshot()['status_code'],200);self.assertFalse(policy_fetch.read_log(d.log))
 def test_429_only_stops_response_host(self):
  with tempfile.TemporaryDirectory() as tmp:
   d=self.make(tmp);d.response(self.response('https://assets2.razerzone.com/widget.js',429,False))
   with self.assertRaisesRegex(BrowserFailure,'rate_limited'):d.snapshot()
   self.assertEqual(set(access_stop.active_stops(policy_fetch.read_log(d.log))),{'assets2.razerzone.com'})
 def test_cooldown_checked_before_navigation(self):
  with tempfile.TemporaryDirectory() as tmp:
   d=self.make(tmp);policy_fetch.record_stop(d.log,'mysupport.razer.com',access_stop.RATE_LIMIT)
   with self.assertRaisesRegex(BrowserFailure,'host_stopped'):d.call('goto',url=d.page.url)
   d.page.goto.assert_not_called()
 def test_200_captcha_never_success(self):
  with tempfile.TemporaryDirectory() as tmp:
   d=self.make(tmp);d.page.content.return_value='<h1>Verify you are human</h1>'
   with self.assertRaisesRegex(BrowserFailure,'challenge_detected'):d.snapshot()
   self.assertIn('mysupport.razer.com',access_stop.active_stops(policy_fetch.read_log(d.log)))
 def test_private_or_foreign_route_blocked(self):
  with tempfile.TemporaryDirectory() as tmp:
   d=self.make(tmp)
   for url in ('https://razer.com/account','https://razer.com/cart','https://evil.test/'):
    route=Mock();route.request.url=url;route.request.is_navigation_request.return_value=False;route.request.method='GET';d.route(route);route.abort.assert_called_once();route.continue_.assert_not_called()
 def test_persistent_profile_requires_visible_mode(self):
  with self.assertRaises(ValueError):PublicBrowserSession(allowed_hosts=('razer.com',),fetch_log_path=Path('unused'),profile_dir=Path('private'))
 def test_attended_positive_observation_resolves_only_temporary_stops(self):
  with tempfile.TemporaryDirectory() as tmp:
   d=self.make(tmp);d.visible=True;d.signal='rate_limited'
   for reason in (access_stop.RATE_LIMIT,access_stop.CHALLENGE,access_stop.MANUAL,access_stop.FATAL,access_stop.HTTP_DENIED):policy_fetch.record_stop(d.log,'mysupport.razer.com',reason)
   policy_fetch.record_stop(d.log,'www.razer.com',access_stop.RATE_LIMIT)
   d.events=[{'status':200,'main_document':True}];d.snapshot(after_manual=True)
   state=access_stop.active_stops(policy_fetch.read_log(d.log));self.assertEqual({r['reason'] for r in state['mysupport.razer.com']},{access_stop.MANUAL,access_stop.FATAL,access_stop.HTTP_DENIED});self.assertIn('www.razer.com',state)
 def test_http_200_without_new_main_response_cannot_clear_rate_limit(self):
  with tempfile.TemporaryDirectory() as tmp:
   d=self.make(tmp);d.visible=True;d.signal='rate_limited';policy_fetch.record_stop(d.log,'mysupport.razer.com',access_stop.RATE_LIMIT);d.events=[{'status':200,'main_document':False}]
   with self.assertRaisesRegex(BrowserFailure,'rate_limited'):d.snapshot(after_manual=True)
   self.assertIn('mysupport.razer.com',access_stop.active_stops(policy_fetch.read_log(d.log)))
 def test_new_stop_after_success_still_blocks(self):
  with tempfile.TemporaryDirectory() as tmp:
   d=self.make(tmp);d.visible=True;d.signal='rate_limited';policy_fetch.record_stop(d.log,'mysupport.razer.com',access_stop.RATE_LIMIT);d.events=[{'status':200,'main_document':True}];d.snapshot(after_manual=True);policy_fetch.record_stop(d.log,'mysupport.razer.com',access_stop.RATE_LIMIT);self.assertIn('mysupport.razer.com',access_stop.active_stops(policy_fetch.read_log(d.log)))
