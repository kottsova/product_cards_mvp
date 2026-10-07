import json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from tests.test_stage62_jbl import page,spec
from product_tool.adapters.jbl import parse_pdp,JBLAdapter
from product_tool.jbl_identity import components
from product_tool import jobs,storage,worker,jbl_pipeline,resolution
R=Path(__file__).resolve().parents[1]/'reports/jbl_stage63'
class Stage63Tests(unittest.TestCase):
 def parse(self,sku,requested='JBLTESTBLKEU',images=None,extra=''):
  return parse_pdp(page(sku,specs=spec('Bluetooth version','5.3'),images=images)+extra,'https://id.jbl.com/x.html',requested)
 def test_generic_color_region_components(self):
  self.assertEqual(components('JBLXTREME4BLUEP')['color'],'Blue');self.assertEqual(components('JBLXTREME4BLUEP')['region'],'EP');self.assertEqual(components('JBLT520BTWHTEU')['model_code'],'JBLT520BT')
 def test_other_color_allows_model_specs_but_not_photo(self):
  d,e=self.parse('JBLTESTBLUEU',images=['https://id.jbl.com/test_blue.png']);self.assertEqual(d.match_level,'model_confirmed');self.assertTrue(d.attributes);self.assertFalse(e['exact_photo_assets']);self.assertEqual(e['identity']['variant_relation'],'other_color')
 def test_other_region_same_color_photo(self):
  d,e=self.parse('JBLTESTBLKAS');self.assertEqual(d.match_level,'model_confirmed');self.assertTrue(e['exact_photo_assets']);self.assertFalse(e['identity']['exact_sku'])
 def test_contradictory_exact_gallery_color_not_confirmed(self):
  d,e=self.parse('JBLTESTBLKEU',images=['https://id.jbl.com/test_white.png']);self.assertTrue(d.attributes);self.assertFalse(e['exact_photo_assets'])
 def test_color_contradicts_returned_sku(self):
  d,e=self.parse('JBLTESTBLUEU',images=['https://id.jbl.com/test_black.png']);self.assertFalse(e['exact_photo_assets'])
 def test_family_support_without_product_not_confirmed(self):
  d,e=parse_pdp('<h1>JBL Test</h1><p>family support</p>','https://support.jbl.com/test.html','JBLTESTBLKEU');self.assertFalse(d.attributes);self.assertFalse(e['identity']['model_confirmed'])
 def test_generation_is_not_region(self):
  d,e=self.parse('JBLTEST2BLKEU');self.assertFalse(d.attributes);self.assertFalse(e['exact_photo_assets'])
 def test_unknown_bundle_suffix_not_stripped(self):
  d,e=self.parse('JBLTESTBLKEU-SET');self.assertFalse(d.attributes)
 def test_model_only_packaging_candidate(self):
  d,e=self.parse('JBLTESTBLKAS',extra='<div class="box-content">Power cable depends on region</div>');self.assertNotIn('Комплектация',[a.name for a in d.attributes]);self.assertTrue(any(x['reason']=='variant_specific_field' for x in e['rejected_specs']))
 def test_real_tune_black_white_same_specs_separate_photos(self):
  rows=[]
  for f,code in [('tune_1.html','JBLT520BTBLKEU'),('tune_white.html','JBLT520BTWHTEU')]:
   d,e=parse_pdp((R/f).read_text(encoding='utf-8'),'https://id.jbl.com/en/over-ear-headphones/'+code[:-2]+'.html',code);rows.append((d,e));self.assertEqual(d.match_level,'model_confirmed');self.assertTrue(e['exact_photo_assets'])
  self.assertEqual([(x.name,x.value) for x in rows[0][0].attributes],[(x.name,x.value) for x in rows[1][0].attributes]);self.assertNotEqual(rows[0][1]['exact_photo_assets'],rows[1][1]['exact_photo_assets'])
 def test_real_bar_usb_and_packaging_not_ported(self):
  d,e=parse_pdp((R/'probe_2.html').read_text(encoding='utf-8'),'https://id.jbl.com/en/soundbars/BAR-500-.html','JBLBAR500PROBLKEP');self.assertEqual(d.match_level,'model_confirmed');self.assertTrue(any(x.name=='Total speaker power output (Max @THD 1%)' for x in d.attributes));self.assertFalse(any('USB' in x.name or 'Packaging' in x.name for x in d.attributes));self.assertTrue(e['rejected_specs'])
 def test_real_xtreme_blue_other_region(self):
  d,e=parse_pdp((R/'probe_1.html').read_text(encoding='utf-8'),'https://id.jbl.com/en/bluetooth-portables/XTREME-4.html','JBLXTREME4BLUEP');self.assertTrue(d.attributes);self.assertTrue(e['exact_photo_assets']);self.assertEqual(e['identity']['color'],'Blue')
 def test_model_resolution_never_sets_full_sku_flag(self):
  fact={'source_key':'jbl','normalized_name':'bluetooth_version','normalized_value':'5.3','unit':''};r=resolution.resolve_attributes([fact],[{'source_key':'jbl','match_level':'model_confirmed','error':''}])[0];self.assertEqual(r.status,'model_confirmed_official');self.assertFalse(r.full_sku_confirmed)
 def test_optional_manual_and_color_readiness(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'db.sqlite3';jobs.initialize(p)
   with storage._connection(p) as db:
    db.execute('INSERT INTO batches VALUES (?,?,?,?,?)',('s63','test','Products','{}',storage._now()));pid=db.execute('INSERT INTO products (batch_id,row_number,name,brand,search_code,alternate_code,category,needs_confirmation,issues_json,original_values_json) VALUES (?,?,?,?,?,?,?,?,?,?)',('s63',1,'JBL Test','JBL','JBLTESTBLKEU','','headphones',0,'[]','{}')).lastrowid
   class Fake(JBLAdapter):
    def find_source(self,article,**kwargs):
     d,e=parse_pdp(page('JBLTESTBLKAS',specs=spec('Bluetooth version','5.3')),'https://id.jbl.com/x.html',article);self.reports[article]=e;return d
   jobs.enqueue(p,pid,[1,2,3,4]);worker.run_once(p,jbl_adapter_factory=lambda:Fake(capture_dir=Path(td)));r=jbl_pipeline.card_readiness(p,pid);self.assertEqual(r['verdict'],'export_ready');self.assertNotIn('manual_unverified',r['blocking_gaps']);self.assertEqual(r['manual_status'],'Не проверена');self.assertFalse(r['exact_sku_identity']);jobs.set_photo_selection(p,pid,[],mode='exact');self.assertEqual(jbl_pipeline.card_readiness(p,pid)['verdict'],'not_ready')
 def test_default_shared_search_after_official_miss(self):
  calls=[];trace=[]
  class HTTP:
   def __init__(self,p):self.log_path=p
   def get(self,url,**kwargs):
    calls.append(('http',url));ok=url=='https://id.jbl.com/observed-model.html';return SimpleNamespace(ok=ok,text=page('JBLTESTBLKAS',specs=spec('Bluetooth version','5.3')) if ok else '',url=url,status_code=200 if ok else 404,marker='')
  class Search:
   def __init__(self,*args,**kwargs):pass
   def search_provider(self,provider,query):calls.append(('search',query));return SimpleNamespace(outcome='candidates_found',candidates=[SimpleNamespace(url='https://id.jbl.com/observed-model.html')])
   def close(self):calls.append(('close',''))
  with tempfile.TemporaryDirectory() as td,patch('product_tool.adapters.lg_browser_search.LGBrowserSearch',Search):
   a=JBLAdapter(session=HTTP(Path(td)/'fetch.json'),capture_dir=Path(td),trace_callback=trace.append);d=a.find_source('JBLTESTBLKEU',name='JBL Test');self.assertEqual(d.match_level,'model_confirmed');self.assertTrue(any(x[0]=='search' for x in calls));self.assertEqual(calls[0][0],'http');self.assertTrue(any(x.get('provider')=='external_search' and x.get('model_relation')=='exact_model' for x in trace));self.assertEqual(calls[-1][0],'close')
 def test_native_official_redirect_model_and_color(self):
  class HTTP:
   def get(self,url,**kwargs):return SimpleNamespace(ok=True,url='https://id.jbl.com/en/bluetooth-portables/XTREME-4.html',text=(R/'native_search_0.html').read_text(encoding='utf-8'),marker='')
  with tempfile.TemporaryDirectory() as td:
   a=JBLAdapter(session=HTTP(),capture_dir=Path(td));d,e=a.regional_search('JBLXTREME4BLUEP','JBL Xtreme 4 Blue',deadline=a.clock()+10);self.assertEqual(d.match_level,'model_confirmed');self.assertTrue(e['exact_photo_assets'])
 def test_native_search_candidate_requires_pdp_revalidation(self):
  class HTTP:
   def get(self,url,**kwargs):
    search='/search?' in url;return SimpleNamespace(ok=True,url=url,text=(R/('native_search_1.html' if search else 'probe_2.html')).read_text(encoding='utf-8'),marker='')
  with tempfile.TemporaryDirectory() as td:
   a=JBLAdapter(session=HTTP(),capture_dir=Path(td));d,e=a.regional_search('JBLBAR500PROBLKEP','JBL Bar 500 Black EP',deadline=a.clock()+10);self.assertEqual(d.match_level,'model_confirmed');self.assertIn('BAR-500-.html',d.url);self.assertTrue(e['exact_photo_assets']);self.assertFalse(e['identity']['exact_sku'])
 def test_model_only_accessory_inclusion_is_variant_candidate(self):
  html=page('JBLTESTBLKAS',specs=spec('Charging cable','Yes')+spec('Bluetooth version','5.3'))
  d,e=parse_pdp(html,'https://id.jbl.com/test.html','JBLTESTBLKEU');self.assertEqual([x.name for x in d.attributes],['Bluetooth version']);self.assertEqual(e['rejected_specs'][0]['reason'],'variant_specific_field')
if __name__=='__main__':unittest.main()
