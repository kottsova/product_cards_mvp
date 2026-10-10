"""Live transport lifecycle, scoped runtime, component and binary/manual controls."""
import hashlib,json,tempfile,time,unittest
from pathlib import Path
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import Mock
import requests
from PIL import Image
from product_tool.adapters.hyperx import HyperXAdapter
from product_tool.adapters.hyperx_support import article_content,verify_guides,category_inventory
from product_tool.adapters.structured_page import extract_dom_spec_table
from product_tool.census.public_browser import PublicBrowserSession
from product_tool.census.search_routes import detect_routes
from product_tool.adapters import access_stop,policy_fetch
from product_tool.hyperx_page import refine_page,canonical_photo_url
from product_tool.hyperx_presentation import label
from product_tool.photo_metadata import inspect_saved_photo
R=Path(__file__).resolve().parents[1]/'reports/hyperx_stage72'

class Stage73Tests(unittest.TestCase):
 def test_published_gallery_cdn_alias_is_stable(self):
  self.assertEqual(canonical_photo_url('https://cdn.shopify.com/s/files/1/0561/8345/5901/files/render.jpg?v=1&width=1600'),'https://hyperx.com/cdn/shop/files/render.jpg?v=1&width=1600')
  other='https://cdn.shopify.com/s/files/1/9999/9999/files/render.jpg?v=1';self.assertEqual(canonical_photo_url(other),other)
 def test_frozen_bytes_equal_prior_stage(self):
  current=R.parent/'hyperx_stage73'
  self.assertEqual((R/'frozen_inputs.json').read_bytes(),(current/'frozen_inputs.json').read_bytes())
 def test_published_search_action(self):
  h='<script type="application/ld+json">'+json.dumps({'@type':'WebSite','potentialAction':{'@type':'SearchAction','target':'https://support.example/search?q={term}','query-input':'required name=term'}})+'</script>'
  routes=detect_routes(h,'https://support.example/',allowed_hosts=('support.example',));self.assertEqual(len(routes),1);self.assertEqual(routes[0].query_url('A B'),'https://support.example/search?q=A+B')
 def test_foreign_search_action_not_executable(self):
  h='<script type="application/ld+json">'+json.dumps({'@type':'SearchAction','target':'https://evil.example/search?q={term}','query-input':'required name=term'})+'</script>'
  self.assertFalse(detect_routes(h,'https://support.example/',allowed_hosts=('support.example',))[0].executable)
 def test_ambiguous_search_action_not_invented(self):
  h='<script type="application/ld+json">'+json.dumps({'@type':'SearchAction','target':'/search?q={term}&x={other}','query-input':'required name=term'})+'</script>'
  self.assertFalse(detect_routes(h,'https://support.example/'))
 def test_same_frequency_preserved_across_components(self):
  h='<table><tr><th colspan="2">Headphone Specifications</th></tr><tr><td>Frequency Response</td><td>20Hz - 20kHz</td></tr><tr><th colspan="2">Microphone Specifications</th></tr><tr><td>Frequency Response</td><td>20Hz - 20kHz</td></tr></table>'
  f=extract_dom_spec_table(h,'https://hyperx.com/test');self.assertEqual(len(f),2);self.assertNotEqual(f[0].section,f[1].section)
 def test_explicit_component_repeat_across_headings_dedupes(self):
  h='<table><tr><th colspan="2">Headphone Specifications</th></tr><tr><td>Boom Mic Polar Pattern</td><td>Uni-directional</td></tr><tr><th colspan="2">Connections and Features</th></tr><tr><td>Boom Mic Polar Pattern</td><td>Uni-directional</td></tr></table>'
  self.assertEqual(len(extract_dom_spec_table(h,'https://hyperx.com/test')),1)
 def test_repeat_within_component_still_dedupes(self):
  h='<table><tr><th colspan="2">Microphone</th></tr>'+('<tr><td>Frequency</td><td>20Hz</td></tr>'*2)+'</table>'
  self.assertEqual(len(extract_dom_spec_table(h,'https://hyperx.com/test')),1)
 def test_runtime_modes_only_explicit_claim(self):
  html=(R/'raw/live_final_1.html').read_text(encoding='utf8');p=json.loads((R/'frozen_inputs.json').read_text(encoding='utf8'))['rows'][0]
  d,e=refine_page(HyperXAdapter().parse_page(html,'https://hyperx.com/test',catalog_code=p['article']),html,'https://hyperx.com/test',p['article'],p['name'])
  modes={r['raw_label']:r['value'] for r in e['runtime_modes']};self.assertEqual(modes['Battery Life (2.4GHz)'],'Up to 250 hours');self.assertEqual(modes['Battery Life (simultaneous connection)'],'125 hours');self.assertNotIn('Battery Life (Bluetooth)',modes);self.assertFalse(any('RGB' in r for r in modes));self.assertEqual(len(e['raw_specs']),len(e['accepted_specs'])+len(e['rejected_specs']))
 def test_unknown_runtime_not_bluetooth(self):
  self.assertIn('режим не указан',label('Battery Life'))
 def test_wired_headset_rejects_wireless_vendor_table(self):
  html=(R/'raw/live_final_2.html').read_text(encoding='utf8');p=json.loads((R/'frozen_inputs.json').read_text(encoding='utf8'))['rows'][1]
  d,e=refine_page(HyperXAdapter().parse_page(html,'https://hyperx.com/test',catalog_code=p['article']),html,'https://hyperx.com/test',p['article'],p['name'])
  rejected={r['raw_label'] for r in e['rejected_specs']};self.assertTrue({'Battery Life','Charge Time','Bit-Depth'}<=rejected)
  self.assertTrue(any(a.name=='Element' and a.section=='Microphone Specifications' for a in d.attributes));self.assertFalse(any(a.name=='Battery Life' for a in d.attributes))
 def test_recording_specs_bound_to_named_model(self):
  html=(R/'raw/live_final_8.html').read_text(encoding='utf8');p=json.loads((R/'frozen_inputs.json').read_text(encoding='utf8'))['rows'][7]
  d,e=refine_page(HyperXAdapter().parse_page(html,'https://hyperx.com/test',catalog_code=p['article']),html,'https://hyperx.com/test',p['article'],p['name'])
  self.assertEqual({a.name:a.value for a in d.attributes if a.name.startswith('Recording')},{'Recording Bit-Depth':'24-bit','Recording Sample Rate':'96 kHz'})
  wrong=html.replace('QuadCast 2 features upgraded','QuadCast 2 S features upgraded')
  _,e=refine_page(HyperXAdapter().parse_page(wrong,'https://hyperx.com/test',catalog_code=p['article']),wrong,'https://hyperx.com/test',p['article'],p['name']);self.assertFalse(e['audio_specs'])
 def test_category_absence_requires_count(self):
  body='<a href="/articles/model/a/1">Model Overview</a>';self.assertFalse(category_inventory(body,'https://supportcenter.hyperx.com/categories/model/cat')[1])
  data={'Community:x':{'conversations({"categoryId":"cat"})':{'totalCount':1}}}
  body+='<script>window.__APOLLO_STATE__ = '+json.dumps(data)+';</script>'
  self.assertTrue(category_inventory(body,'https://supportcenter.hyperx.com/categories/model/cat')[1])
 def test_user_guide_classifier_recognizes_actual_heading(self):
  from product_tool.adapters.lg_documents import assess_document
  text='Example User Guide. Руководство. Connecting the controls. Press the power button. '
  self.assertTrue(assess_document([text],['Example'])['accepted'])
 def test_article_node_binding_not_related_preview(self):
  data={'Conversation:x':{'id':'x','title':'Wrong guide','content':'wrong'},'Conversation:y':{'id':'y','title':'Right guide','parsedContent':'<p>right</p>'}}
  html='<script>window.__APOLLO_STATE__ = '+json.dumps(data)+';</script>'
  self.assertEqual(article_content(html,'https://supportcenter.hyperx.com/articles/a/y'),('Right guide','<p>right</p>'))
 def test_safety_never_primary_manual(self):
  docs,status,_=verify_guides([{'title':'HyperX Example Safety','type':'Safety','url':'https://supportcenter.hyperx.com/a','download_candidates':[],'article_content':'','verified':False}],'HyperX Example','123',lambda _:self.fail('Safety must not become a guide'))
  self.assertFalse(docs);self.assertEqual(status,'Не проверена')
 def test_failed_pdf_is_technical_unchecked(self):
  guide={'title':'HyperX Example Quick Start Guide','type':'Quick Start Guide','url':'https://supportcenter.hyperx.com/a','download_candidates':['https://files.hyperx.com/a.pdf'],'article_content':'','verified':False}
  def fail(_):raise ConnectionError('external network error')
  docs,status,technical=verify_guides([guide],'HyperX Example','123',fail);self.assertFalse(docs);self.assertEqual(status,'Не проверена');self.assertTrue(technical)
 def route(self,method='POST',query='query PublicSearch { search { title } }',url='https://supportcenter.hyperx.com/schema/community'):
  b=PublicBrowserSession(allowed_hosts=('supportcenter.hyperx.com',),fetch_log_path=Path('unused'),allow_readonly_graphql=True,readonly_graphql_paths=('/schema/community',),pause=lambda _:None)
  b.started=time.monotonic();r=Mock();r.request=SimpleNamespace(url=url,method=method,resource_type='xhr',post_data=json.dumps({'query':query}),is_navigation_request=lambda:False)
  b.route(r);return r
 def test_readonly_graphql_admitted(self):self.route().continue_.assert_called_once()
 def test_graphql_mutation_rejected(self):self.route(query='mutation { deleteAccount }').abort.assert_called_once()
 def test_foreign_graphql_rejected(self):self.route(url='https://evil.example/schema/community').abort.assert_called_once()
 def test_binary_active_stop_zero_network(self):
  with tempfile.TemporaryDirectory() as td:
   b=PublicBrowserSession(allowed_hosts=('hyperx.com',),fetch_log_path=Path(td)/'log.json');policy_fetch.record_stop(b.log,'hyperx.com',access_stop.RATE_LIMIT)
   b.start=Mock(side_effect=AssertionError('no browser started'))
   with self.assertRaises(requests.ConnectionError):b.binary_transport().get('https://hyperx.com/a.png')
   b.start.assert_not_called()
 def test_verified_assets_survive_failed_manual_recheck(self):
  from product_tool import jobs,worker,card_evidence
  from product_tool.adapters.common import SourceDocument,ProductDocument,PhotoCandidate
  from product_tool.adapters.hyperx import ScopedAttribute,format_attribute_scope
  from tests.test_hyperx_worker_integration import seed_product,NoOpDnsAdapter
  with tempfile.TemporaryDirectory() as td:
   db=Path(td)/'db.sqlite3';pid=seed_product(db,sku='9A273AA',name='HyperX QuadCast 2 S')
   attrs=[ScopedAttribute('Frequency Response','20Hz - 20kHz',scope='model'),ScopedAttribute('Polar Pattern','Cardioid',scope='model'),ScopedAttribute('Connection Type','USB-C',scope='model')]
   photo=PhotoCandidate('https://hyperx.com/photo.png','asset')
   doc=SourceDocument('hyperx','HyperX','https://hyperx.com/products/example',match_level='exact_variant',attributes=attrs,evidence=format_attribute_scope([],attrs),photo_candidates=[photo])
   jobs.save_source_document(db,pid,doc);jobs.save_documents(db,pid,'hyperx',[ProductDocument('Verified User Guide','ru','','100 B','https://files.hyperx.com/guide.pdf',doc.url,'QuadCast 2 S','QuadCast 2 S',doc.url,True)])
   p=jobs.get_photo_candidates(db,pid)[0];jobs.save_photo_metadata(db,pid,p['id'],p['url'],width=1000,height=1000,size_bytes=100,image_format='PNG');jobs.set_photo_selection(db,pid,['asset'])
   card_evidence.save(db,pid,'hyperx',{'manual_status':'Проверена','manuals':[{'verified':True,'title':'Verified User Guide'}],'byte_verified_gallery':[{'asset_key':'asset','verified':True}]})
   class Adapter:
    discovery_enabled=True;source_key='hyperx';site_name='HyperX'
    def __init__(self):self.reports={}
    def find_source(self,code,**kwargs):
     self.reports[code]={'model_relation':'model_confirmed','configuration_relation':'exact_variant','exact_photo_assets':['asset'],'manual_status':'Не проверена'};return doc
    def find_documents(self,code,**kwargs):
     self.reports[code].update(manual_status='Не проверена',manuals=[],manual_reason='temporary technical failure');return [],'temporary technical failure'
   a=Adapter();jobs.enqueue(db,pid,[1,2,3,4,6]);worker.run_once(db,hyperx_adapter_factory=lambda:a,dns_adapter_factory=NoOpDnsAdapter)
   self.assertEqual(len(jobs.get_documents(db,pid)),1);self.assertEqual(jobs.get_photo_candidates(db,pid)[0]['verified_bytes'],100)
   e=card_evidence.load(db,pid,'hyperx');self.assertEqual(e['manual_status'],'Проверена');self.assertEqual(e['manual_current_attempt']['manual_status'],'Не проверена')
 def test_system_ca_env_restored(self):
  import os
  from unittest.mock import patch
  seen=[];page=Mock();context=Mock();context.pages=[page];driver=Mock();driver.chromium.launch.return_value.new_context.return_value=context
  class Manager:
   def __enter__(self):seen.append(os.environ.get('NODE_USE_SYSTEM_CA'));return driver
   def __exit__(self,*args):pass
  with patch.dict(os.environ,{'NODE_USE_SYSTEM_CA':'prior'}):
   b=PublicBrowserSession(allowed_hosts=('hyperx.com',),fetch_log_path=Path('unused'),use_system_ca=True,playwright_factory=Manager);b.start();b.close();self.assertEqual(seen,['1']);self.assertEqual(os.environ['NODE_USE_SYSTEM_CA'],'prior')
 def measure(self,data,ct='image/png'):
  class Session:
   headers={}
   def get(self,url,**kwargs):
    r=requests.Response();r.url=url;r.status_code=200;r.headers['content-type']=ct;r._content=data;r._content_consumed=True;return r
  with tempfile.TemporaryDirectory() as td:return inspect_saved_photo('https://hyperx.com/render.png','hyperx',Path(td)/'log.json',underlying=Session())
 def image(self,blank=False):
  im=Image.new('RGB',(100,80),'white')
  if not blank:im.putpixel((50,40),(0,0,0))
  buf=BytesIO();im.save(buf,format='PNG');return buf.getvalue()
 def test_real_image_bytes_measured(self):
  data=self.image();m=self.measure(data);self.assertEqual((m['width'],m['height']),(100,80));self.assertEqual(m['content_type'],'image/png');self.assertEqual(m['sha256'],hashlib.sha256(data).hexdigest())
 def test_truncated_image_rejected(self):
  with self.assertRaises(ValueError):self.measure(self.image()[:24])
 def test_placeholder_rejected(self):
  with self.assertRaises(ValueError):self.measure(self.image(True))
 def test_wrong_image_content_type_rejected(self):
  with self.assertRaises(ValueError):self.measure(self.image(),'text/html')

if __name__=='__main__':unittest.main()
