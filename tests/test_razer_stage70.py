"""Razer variant leakage, conditional laptop tables and browser stop controls."""
import ast,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch,Mock
from product_tool.razer_identity import model_relation,components
from product_tool.razer_page import parse_page
from product_tool.adapters.razer import RazerAdapter
from product_tool.adapters import policy_fetch,access_stop
from product_tool import razer_pipeline
from product_tool.census.browser_runtime import BrowserFailure
URL='https://www.razer.com/gaming-mice/razer-example'
CODE='RZ01-99990100-R3U1'
def page(props=(),images=(),sku=CODE,name='Razer Example',extra=''):
 product={'@type':'Product','name':name,'sku':sku,'image':list(images),'additionalProperty':[{'name':k,'value':v} for k,v in props]}
 return '<title>'+name+'</title><h1>'+name+'</h1><script type="application/ld+json">'+json.dumps(product)+'</script>'+extra
class IdentityTests(unittest.TestCase):
 def test_opaque_suffix(self):self.assertFalse(components(CODE)['suffix_decoded']);self.assertEqual(components(CODE)['regional_suffix'],'R3U1')
 def test_model_prefix_needs_same_commercial_name(self):
  self.assertTrue(model_relation('RZ03-9999','Razer Example','Razer Example | RZ03-99990 Support & FAQs')['model_confirmed']);self.assertFalse(model_relation('RZ03-9999','Razer Example','Razer Example Pro | RZ03-99990 Support & FAQs')['model_confirmed'])
 def test_wired_wireless_not_same(self):self.assertFalse(model_relation('RZ01-9999','Razer Example','Razer Example Wireless | RZ01-9999 Support & FAQs')['model_confirmed'])
 def test_generation_not_same(self):self.assertFalse(model_relation('RZ01-9999','Razer Example (2023)','Razer Example (2020) | RZ01-9999 Support & FAQs')['model_confirmed'])
 def test_other_regional_suffix_not_exact(self):
  d,e=parse_page(page(sku='RZ01-99990100-R3M1'),URL,CODE,'Razer Example','Мыши');self.assertFalse(e['identity']['exact_sku'])
 def test_url_code_alone_never_identity(self):
  d,e=parse_page('<title>Something</title>',URL+'/'+CODE,CODE,'Razer Example','Мыши');self.assertFalse(e['identity']['model_confirmed'])
class ExtractionTests(unittest.TestCase):
 def test_programmable_controls_not_ram(self):
  from product_tool.razer_identity import configuration_sensitive
  self.assertFalse(configuration_sensitive('Programmable Controls'));self.assertTrue(configuration_sensitive('RAM'))
 def test_long_axis_names_keep_mm_before_inches(self):
  html='<title>Razer Example | RZ01-9999 Support & FAQs</title><div id="at-a-glance"><table><tr><th>Approx. Dimensions</th><td>Length: 127.1 mm / 5.00 in Width: 63.9 mm / 2.51 in Height: 39.9 mm / 1.57 in</td></tr></table></div>'
  d,e=parse_page(html,'https://mysupport.razer.com/app/answers/detail/a_id/1','RZ01-9999','Razer Example','Мыши');self.assertEqual([(x.name,x.value) for x in d.attributes],[('Ширина','63.9 mm'),('Высота','39.9 mm'),('Глубина','127.1 mm')]);self.assertEqual(len(e['raw_specs']),len(e['accepted_specs'])+len(e['rejected_specs']))
 def test_single_returned_exact_product(self):
  d,e=parse_page(page([('Sensor','Focus Pro')]),URL,CODE,'Razer Example','Мыши');self.assertTrue(e['identity']['exact_sku']);self.assertEqual(d.attributes[0].name,'Сенсор')
 def test_color_mismatch_never_confirmed(self):
  d,e=parse_page(page([('Color','Black')]),URL,CODE,'Razer Example [color=White]','Мыши');self.assertEqual(e['identity']['configuration_relation'],'unproven');self.assertFalse(d.attributes)
 def test_wrong_keyboard_layout(self):
  d,e=parse_page(page([('Layout','US')]),URL,CODE,'Razer Example [layout=UK]','Клавиатуры');self.assertEqual(e['identity']['configuration_relation'],'unproven');self.assertFalse(d.attributes)
 def test_switch_options_are_candidates(self):
  html='<title>Razer Example | RZ03-9999 Support & FAQs</title><div id="at-a-glance"><table><tr><th>Switch Type</th><td>Orange or Yellow</td></tr></table></div>'
  d,e=parse_page(html,'https://mysupport.razer.com/app/answers/detail/a_id/1','RZ03-9999','Razer Example [switch=Orange]','Клавиатуры');self.assertFalse(d.attributes);self.assertEqual(e['rejected_specs'][0]['reason'],'configuration_specific')
 def test_laptop_hidden_selector_does_not_confirm_default(self):
  html='<title>Razer Example | RZ09-9999 Support & FAQs</title><div id="at-a-glance"><table><tr><th>Installed</th><td><p data-arr="g1">1 TB</p><p data-arr="g2" hidden>2 TB</p></td></tr><tr><th>CPU</th><td>A</td></tr></table></div>'
  d,e=parse_page(html,'https://mysupport.razer.com/app/answers/detail/a_id/1','RZ09-9999','Razer Example [storage=1 TB]','Ноутбуки');self.assertFalse(d.attributes);self.assertEqual(len(e['rejected_specs']),2)
 def test_battery_polling_modes_and_up_to_retained(self):
  html='<title>Razer Example | RZ01-9999 Support & FAQs</title><div id="at-a-glance"><table><tr><th>Battery Life</th><td><ul><li>Up to 95 hours at 1000 Hz</li><li>Up to 17 hours at 8000 Hz</li></ul></td></tr></table></div>'
  d,e=parse_page(html,'https://mysupport.razer.com/app/answers/detail/a_id/1','RZ01-9999','Razer Example','Мыши');self.assertEqual(len(d.attributes),2);self.assertIn('1000 Hz',d.attributes[0].name);self.assertIn('Up to',d.attributes[1].value)
 def test_scoped_specs_no_warranty_faq_description(self):
  html='<title>Razer Example | RZ01-9999 Support & FAQs</title><div id="at-a-glance"><table><tr><th>Sensor</th><td>Focus Pro</td></tr></table></div><table><tr><td>Warranty</td><td>2 years</td></tr></table><p>Firmware update reset repair</p>'
  d,e=parse_page(html,'https://mysupport.razer.com/app/answers/detail/a_id/1','RZ01-9999','Razer Example','Мыши');self.assertEqual(len(d.attributes),1);self.assertEqual(d.description,'');self.assertEqual(len(e['raw_specs']),1)
 def test_exact_product_image_but_other_color_candidate(self):
  d,e=parse_page(page([('Color','Black')],['https://assets2.razerzone.com/example-white.png']),URL,CODE,'Razer Example [color=Black]','Мыши');self.assertFalse(e['exact_photo_assets']);self.assertEqual(len(d.photo_candidates),1)
 def test_other_layout_photo_candidate(self):
  d,e=parse_page(page([('Layout','US')],['https://assets2.razerzone.com/example-uk.png']),URL,CODE,'Razer Example [layout=US]','Клавиатуры');self.assertFalse(e['exact_photo_assets'])
 def test_exact_gallery_can_be_verified(self):
  d,e=parse_page(page([('Color','Black')],['https://assets2.razerzone.com/example-black.png']),URL,CODE,'Razer Example [color=Black]','Мыши');self.assertEqual(len(e['exact_photo_assets']),1)
 def test_multi_product_blocks_not_exact(self):
  d,e=parse_page(page()+page(name='Other'),URL,CODE,'Razer Example','Мыши');self.assertFalse(e['identity']['exact_sku'])
 def test_explicit_dimensions(self):
  html='<title>Razer Example | RZ01-9999 Support & FAQs</title><div id="at-a-glance"><table><tr><th>Approx. Dimension</th><td>L: 5 in / 128 mm W: 2.67 in / 68 mm H: 1.73 in / 44 mm</td></tr></table></div>'
  d,e=parse_page(html,'https://mysupport.razer.com/app/answers/detail/a_id/1','RZ01-9999','Razer Example','Мыши');self.assertEqual([(x.name,x.value) for x in d.attributes],[('Ширина','68 mm'),('Высота','44 mm'),('Глубина','128 mm')])
 def test_foreign_host_rejected(self):
  d,e=parse_page(page([('Sensor','A')]),'https://dealer.example/item',CODE,'Razer Example','Мыши');self.assertFalse(d.attributes)
class StopTests(unittest.TestCase):
 def test_support_429_persisted_and_no_second_browser(self):
  with tempfile.TemporaryDirectory() as tmp:
   log=Path(tmp)/'fetch.json';driver=Mock();driver.call.side_effect=BrowserFailure('rate_limited',{'rate_limit_url':'https://mysupport.razer.com/app/answers/list/kw/example'});factory=Mock(return_value=driver);a=RazerAdapter(fetch_log_path=log,browser_factory=factory);self.assertIsNone(a.render_support('https://mysupport.razer.com/app/answers/list/kw/example','example'));self.assertIsNone(a.render_support('https://mysupport.razer.com/app/answers/list/kw/other','other'));self.assertEqual(factory.call_count,1);self.assertIn('mysupport.razer.com',access_stop.active_stops(policy_fetch.read_log(log)))
 def test_manual_optional_when_existing_thresholds_met(self):
  ev={'identity':{'model_relation':'model_confirmed'},'exact_photo_assets':['x'],'manual_status':'Не проверена'};facts=[{'status':'model_confirmed_official','conflict':False,'selected_source':'razer_model'}]*3
  with patch.object(razer_pipeline.card_evidence,'load',return_value=ev),patch.object(razer_pipeline.jobs,'get_resolved',return_value=facts),patch.object(razer_pipeline.jobs,'result_counts',return_value={'conflicts':0}),patch.object(razer_pipeline.jobs,'get_photo_candidates',return_value=[{'selected':True,'asset_key':'x','kind':'product_gallery'}]):
   r=razer_pipeline.card_readiness(Path('unused'),1);self.assertEqual(r['verdict'],'export_ready');self.assertEqual(r['advisory_gaps'],['manual_unverified'])
class SnapshotTests(unittest.TestCase):
 def command(self,html,mode='render_existing_search_result',guard=None):
  tree=ast.parse(Path('product_tool/census/browser_worker.py').read_text(encoding='utf8'));fn=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='command');module=ast.Module(body=[fn],type_ignores=[]);page=Mock();page.content.return_value=html;env={'guard':guard or Mock(),'state':lambda:{},'policy':{'render_mode':mode,'max_dom_bytes':10},'page':page};exec(compile(module,'browser_worker','exec'),env);return env['command']({'command':'document_snapshot'})
 def test_snapshot_is_bounded(self):
  self.assertEqual(self.command('hello')['html'],'hello')
  with self.assertRaisesRegex(RuntimeError,'projection_budget_exhausted'):self.command('x'*11)
 def test_snapshot_cannot_ignore_challenge(self):
  with self.assertRaisesRegex(RuntimeError,'challenge_detected'):self.command('x',guard=Mock(side_effect=RuntimeError('challenge_detected')))
 def test_snapshot_not_available_in_interactive_flow(self):
  with self.assertRaisesRegex(RuntimeError,'interaction_blocked'):self.command('x',mode='interactive_search_ui')
class DispatchTests(unittest.TestCase):
 def test_ordinary_run_once_uses_razer_adapter_and_shared_persistence(self):
  from product_tool import jobs,worker
  from product_tool.adapters.common import SourceDocument,RawAttribute,PhotoCandidate
  from tests.test_dns_fallback import seed_product
  with tempfile.TemporaryDirectory() as tmp:
   db=Path(tmp)/'batches.sqlite3';jobs.initialize(db);pid=seed_product(db,brand='Razer',sku='RZ01-9999',name='Razer Example');jobs.enqueue(db,pid,[1,3,4])
   adapter=Mock();adapter.reports={'RZ01-9999':{'identity':{'model_relation':'model_confirmed'},'exact_photo_assets':['image-x'],'manual_status':'Не проверена'}};adapter.find_source.return_value=SourceDocument('razer_model','Razer Official','https://mysupport.razer.com/app/answers/detail/a_id/1',found_model='RZ01-9999',match_level='model_confirmed',attributes=[RawAttribute('Сенсор','Focus Pro'),RawAttribute('Частота опроса','8000 Hz'),RawAttribute('Подключение','USB')],photo_candidates=[PhotoCandidate('https://assets2.razerzone.com/example.png','image-x')]);dealer=Mock()
   self.assertTrue(worker.run_once(db,razer_adapter_factory=lambda:adapter,dns_adapter_factory=dealer));self.assertEqual(adapter.find_source.call_count,1);dealer.assert_not_called();self.assertEqual(jobs.list_jobs(db,pid)[0]['status'],'done');self.assertEqual(razer_pipeline.card_readiness(db,pid)['verdict'],'export_ready')
