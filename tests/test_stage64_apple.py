import unittest,json
from pathlib import Path
from product_tool.adapters.apple import parse_page,official
from product_tool.resolution import resolve_attributes
ROOT=Path(__file__).resolve().parents[1]/'reports/apple_stage64'
class AppleIdentityTests(unittest.TestCase):
 def parse(self,article='FW123LL/A',file='official_0.html',url='https://www.apple.com/shop/product/fw123ll/a'):
  return parse_page((ROOT/file).read_text(encoding='utf-8'),url,article)
 def test_exact_order_config(self):
  doc,ev=self.parse();self.assertEqual(doc.match_level,'full_sku');self.assertTrue(ev['configuration_complete']);self.assertTrue(doc.photo_candidates)
 def test_other_commercial_storage_sku(self):
  doc,ev=self.parse('FC6U4LL/A');self.assertNotEqual(doc.match_level,'full_sku');self.assertFalse(doc.attributes);self.assertFalse(doc.photo_candidates)
 def test_other_regional_sku(self):
  doc,ev=self.parse('FW123CL/A');self.assertNotEqual(doc.match_level,'full_sku');self.assertFalse(doc.attributes)
 def test_hardware_model_not_order_number(self):
  doc,ev=self.parse('A3240');self.assertNotEqual(doc.match_level,'full_sku');self.assertFalse(doc.attributes)
 def test_same_model_colors_separate_selection(self):
  a,black=self.parse('MYAP3LL/A','official_5.html','https://www.apple.com/shop/buy-iphone/iphone-16');b,white=self.parse('MYAQ3LL/A','official_5.html','https://www.apple.com/shop/buy-iphone/iphone-16')
  self.assertNotEqual(black['selected_configuration']['dimensionColor'],white['selected_configuration']['dimensionColor']);self.assertTrue(a.photo_candidates);self.assertTrue(b.photo_candidates);self.assertNotEqual(a.photo_candidates[0].url,b.photo_candidates[0].url);self.assertFalse(a.attributes)
 def test_family_specs_not_exact_config(self):
  doc,ev=self.parse('MYAP3LL/A','official_2.html','https://support.apple.com/en-us/121031');self.assertFalse(doc.attributes);self.assertFalse(doc.photo_candidates);self.assertNotEqual(doc.match_level,'full_sku')
 def test_fake_official_host(self):
  doc,ev=self.parse(url='https://apple.com.attacker.test/p');self.assertTrue(doc.error);self.assertFalse(doc.attributes)
 def test_empty_shell(self):
  doc,ev=parse_page('<html><h1>MacBook Air</h1></html>','https://www.apple.com/shop/product/fw123ll/a','FW123LL/A');self.assertFalse(doc.attributes)
 def test_metric_dimensions(self):
  doc,ev=self.parse();dims={x.name:x.value for x in doc.attributes if x.section=='Size and Weight'};self.assertEqual(float(dims['Вес товара, кг']),1.24);self.assertAlmostEqual(float(dims['Ширина товара, мм']),304.1)
 def test_runtime_modes_separate(self):
  doc,ev=self.parse();names={x.name for x in doc.attributes};self.assertIn('Время потокового воспроизведения видео',names);self.assertIn('Время работы в интернете',names)
 def test_exact_apple_resolution_is_official(self):
  facts=[dict(source_key='apple',normalized_name='storage',normalized_value='256',unit='GB')];p=[dict(source_key='apple',match_level='full_sku',error='')];out=resolve_attributes(facts,p);self.assertTrue(out[0].full_sku_confirmed)
 def test_multiple_offer_skus_not_single_order(self):
  html='<h1>iPhone 16</h1><script type="application/ld+json">'+json.dumps({'@type':'Product','offers':[{'@type':'Offer','sku':'MYAP3LL/A'},{'@type':'Offer','sku':'MYAQ3LL/A'}]})+'</script>'
  doc,ev=parse_page(html,'https://www.apple.com/shop/buy-iphone/iphone-16','MYAP3LL/A');self.assertNotEqual(doc.match_level,'full_sku');self.assertFalse(doc.photo_candidates)
 def test_conflicting_gallery_color_is_candidate(self):
  html=(ROOT/'official_0.html').read_text(encoding='utf-8').replace('refurb-mba13-m4-midnight','refurb-mba13-m4-silver')
  doc,ev=parse_page(html,'https://www.apple.com/shop/product/fw123ll/a','FW123LL/A');self.assertFalse(doc.photo_candidates);self.assertTrue(ev['photo_candidates'])
 def test_real_ipad_gallery_box_and_multicolor_are_candidates(self):
  records=[p for p in (ROOT/'apple_captures').glob('*.html.json') if json.loads(p.read_text(encoding='utf-8'))['query']=='FD3Y4LL/A'];self.assertTrue(records)
  record=records[0];meta=json.loads(record.read_text(encoding='utf-8'));doc,ev=parse_page(record.with_suffix('').read_text(encoding='utf-8'),meta['url'],'FD3Y4LL/A')
  self.assertEqual(len(doc.photo_candidates),2);self.assertTrue(any('Packaging' in x['reason'] for x in ev['photo_candidates']));self.assertTrue(any('multiple' in x['reason'] for x in ev['photo_candidates']))
