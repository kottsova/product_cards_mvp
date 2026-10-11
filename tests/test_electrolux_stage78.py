"""Actual native SSR fixture tests; offline success is never claimed as live."""
import hashlib,json,unittest
import tempfile
from types import SimpleNamespace
from pathlib import Path
from bs4 import BeautifulSoup
from product_tool.electrolux_page import parse,payload,catalog_links,official,mapped
ROOT=Path(__file__).resolve().parents[1]/'reports/electrolux_stage78'
URL='https://www.electrolux.co.uk/kitchen/cooking/ovens/oven/eof6p46x/'
def native():return (ROOT/(hashlib.sha256(URL.encode()).hexdigest()[:12]+'.html')).read_text(encoding='utf8')
def changed(fn):
 s=BeautifulSoup(native(),'html.parser');node=s.select_one('#__NEXT_DATA__');d=json.loads(node.string);fn(d['props']['pageProps']['pageData']);node.string=json.dumps(d).replace('<','\\u003c');return str(s)
class ElectroluxStage78(unittest.TestCase):
 def test_native_owner(self):
  doc,ev=parse(native(),URL,'EOF6P46X');self.assertEqual(doc.match_level,'full_sku');self.assertEqual(ev['identity']['product_code'],'944032051');self.assertIsNone(ev['identity']['revision']);self.assertGreater(len(doc.attributes),20)
 def test_nine_digit_pnc(self):
  doc,ev=parse(native(),URL,'EOF6P46X','944032051','UK');self.assertTrue(ev['identity']['configuration_confirmed'])
 def test_revision_never_padded(self):
  doc,ev=parse(native(),URL,'EOF6P46X','94403205100','UK');self.assertEqual(ev['identity']['product_code_relation'],'base_pnc_partial');self.assertNotIn('Напряжение питания, В',[a.name for a in doc.attributes]);self.assertFalse(any(p['eligible'] for p in ev['gallery_inventory']))
 def test_other_pnc_energy_rejected(self):
  doc,ev=parse(native(),URL,'EOF6P46X','944032052','UK');self.assertFalse(ev['identity']['configuration_confirmed']);self.assertTrue(any(r['label']=='Energy Rating' for r in ev['rejected_facts']));self.assertNotIn('Вес товара, кг',[a.name for a in doc.attributes])
  self.assertFalse(any(f.section=='Программы' for f in doc.attributes))
 def test_different_region(self):
  doc,ev=parse(native(),URL,'EOF6P46X','','DE');self.assertEqual(doc.match_level,'model_confirmed');self.assertFalse(ev['identity']['configuration_confirmed'])
 def test_color_not_transferred(self):
  doc,ev=parse(native(),URL,'EOF6P46X','','UK','Black');self.assertFalse(ev['identity']['configuration_confirmed']);self.assertNotIn('Цвет / отделка',[a.name for a in doc.attributes]);self.assertFalse(any(p['eligible'] for p in ev['gallery_inventory']))
 def test_product_and_niche(self):
  doc,ev=parse(native(),URL,'EOF6P46X');fields={f.name:f.value for f in doc.attributes};self.assertEqual(fields['Ширина товара, мм'],'595');self.assertEqual(fields['Ширина ниши, мм'],'560');self.assertEqual(fields['Высота ниши, мм'],'590');self.assertEqual(fields['Вес с упаковкой, кг'],'35.5')
 def test_energy_periods_preserved(self):
  a=mapped({'label':'Annual Energy Consumption (kWh)','value':'235','section':'Energy'});b=mapped({'label':'Energy Consumption per 100 wash cycles (kWh)','value':'51','section':'Energy'});self.assertNotEqual(a[0].name,b[0].name);self.assertNotIn('A++',a[0].value)
 def test_program_parent_one_field(self):
  doc,ev=parse(native(),URL,'EOF6P46X');programs=[f for f in doc.attributes if f.section=='Программы'];self.assertEqual(len(programs),1);self.assertIn('Turbo grilling',programs[0].value)
 def test_support_not_description(self):
  doc,ev=parse(native(),URL,'EOF6P46X');self.assertNotIn('troubleshoot',doc.description.lower());self.assertNotIn('Register',doc.description);self.assertTrue(doc.description.startswith('With the 600'))
 def test_organization_ld_not_product(self):
  doc,ev=parse(native(),URL,'EOF6P46X');self.assertNotEqual(doc.found_model,'Electrolux United Kingdom');self.assertNotIn('customer support',[f.name for f in doc.attributes])
 def test_family_not_exact(self):
  html=changed(lambda d:d['components'].__setitem__(1,{'name':'ProductList','props':{}}));doc,ev=parse(html,URL,'EOF6P46X');self.assertEqual(ev['identity']['model_relation'],'unproven');self.assertEqual(doc.attributes,[])
 def test_wrong_owner_model(self):
  doc,ev=parse(native(),URL,'EOF6P46K');self.assertEqual(doc.match_level,'mismatch');self.assertEqual(doc.attributes,[])
 def test_mismatched_owner_pnc(self):
  html=changed(lambda d:d['components'][1]['props'].__setitem__('productCode','944032052'));doc,ev=parse(html,URL,'EOF6P46X');self.assertTrue(doc.error);self.assertEqual(doc.attributes,[])
 def test_document_types(self):
  doc,ev=parse(native(),URL,'EOF6P46X');types={d['type'] for d in ev['document_inventory']};self.assertTrue({'User Manual','Product Fiche','Energy Label','Specification Sheet'}<=types);self.assertFalse(any(d['bytes_verified'] for d in ev['document_inventory']))
 def test_documents_wrong_pnc(self):
  def edit(d):
   docs=d['components'][1]['components'][3]['components'][2]['props'];docs['productCode']='944032052'
  _,ev=parse(changed(edit),URL,'EOF6P46X');self.assertFalse(any(d['identity_verified'] for d in ev['document_inventory']))
 def test_document_model_and_pnc_fields_have_different_roles(self):
  def edit(d):
   docs=d['components'][1]['components'][3]['components'][2]['props'];docs['productCode']='EOF6P46X';docs['pnc']='944032051'
  _,ev=parse(changed(edit),URL,'EOF6P46X');self.assertTrue(all(d['identity_verified'] for d in ev['document_inventory']))
 def test_energy_url_other_pnc_is_candidate(self):
  def edit(d):
   docs=d['components'][1]['components'][3]['components'][2]['props']['document']['documents']
   for x in docs:
    if x['name']=='energy label':x['url']=x['url'].replace('944032051','944032052')
  _,ev=parse(changed(edit),URL,'EOF6P46X');self.assertFalse(next(d['identity_verified'] for d in ev['document_inventory'] if d['type']=='Energy Label'))
 def test_no_faq_facts(self):
  doc,ev=parse(native(),URL,'EOF6P46X');self.assertTrue(ev['rejected_facts']);self.assertFalse(any(r['section']=='Specification' for r in ev['accepted_facts']))
 def test_catalog_redirect_not_live_pdp(self):
  u='https://www.electrolux.co.uk/laundry/laundry/washing-machines/front-loader-washing-machine/efi61141b/';html=(ROOT/(hashlib.sha256(u.encode()).hexdigest()[:12]+'.html')).read_text(encoding='utf8');doc,ev=parse(html,u,'EFI61141B');self.assertEqual(ev['identity']['model_relation'],'unproven');self.assertTrue(catalog_links(html,u,'EFI61141B'))
 def test_official_url_boundary(self):
  self.assertTrue(official(URL));self.assertFalse(official('https://electrolux.co.uk.evil.test/p'));self.assertFalse(official('https://:pass@www.electrolux.co.uk/p'))
 def test_depth_max_qualifier(self):
  out=mapped({'label':'Dimensions (mm) (HxWxD)','value':'850x596x662(max)','section':'Other'});self.assertEqual(out[-1].value,'662 (макс.)')
 def test_shared_normalization_installation_scopes(self):
  from product_tool.normalization import normalize_fact
  from product_tool.adapters.common import RawAttribute
  product=normalize_fact(RawAttribute('Ширина товара, мм','595 мм','Габариты товара'))
  niche=normalize_fact(RawAttribute('Ширина ниши, мм','560 мм','Встраивание'))
  self.assertEqual(product.normalized_name,'product_dimensions__width');self.assertEqual(niche.normalized_name,'installation_dimensions__width');self.assertNotEqual(product.normalized_name,niche.normalized_name)
 def test_led_color_is_not_product_finish(self):
  from product_tool.normalization import normalize_fact
  a=normalize_fact(mapped({'label':'LED Colour','value':'Red','section':'Installation'})[0]);b=normalize_fact(mapped({'label':'Main Colour','value':'Black','section':'Other'})[0]);self.assertNotEqual(a.normalized_name,b.normalized_name)
 def test_bare_machine_weight_is_not_net_weight(self):
  from product_tool.normalization import normalize_fact
  a=normalize_fact(mapped({'label':'Vikt, endast maskin kg','value':'4.998','section':'Installation'})[0]);b=normalize_fact(mapped({'label':'Nettovikt, kg','value':'7.273','section':'Installation'})[0]);self.assertNotEqual(a.normalized_name,b.normalized_name)
class BinaryRedirectStage78(unittest.TestCase):
 def transport(self,responses,log):
  from product_tool.census.public_browser import PublicBrowserSession
  class Response:
   def __init__(self,url,status,headers,raw=b'%PDF-test'):self.url=url;self.status=status;self.headers=headers;self.raw=raw;self.disposed=False
   def body(self):return self.raw
   def dispose(self):self.disposed=True
  class API:
   def __init__(self):self.calls=[]
   def get(self,url,**kwargs):
    self.calls.append(url);assert kwargs['max_redirects']==0
    status,headers=responses[url];return Response(url,status,headers)
  b=PublicBrowserSession(allowed_hosts=('electrolux.co.uk','electroluxgroup.eu'),fetch_log_path=log,pause=lambda _:None);api=API();b.context=SimpleNamespace(request=api);b.start=lambda:None;return b.binary_transport(),api
 def test_safe_redirect_is_followed_and_traced(self):
  with tempfile.TemporaryDirectory() as td:
   first='https://support.electroluxgroup.eu/pdf';last='https://www.electrolux.co.uk/pdf';t,api=self.transport({first:(301,{'location':last}),last:(200,{'content-type':'application/pdf'})},Path(td)/'log.json');r=t.get(first,allow_redirects=True);self.assertEqual(r.content,b'%PDF-test');self.assertEqual(r.url,last);self.assertEqual([x.url for x in r.history],[first]);self.assertEqual(api.calls,[first,last])
 def test_foreign_redirect_never_requested(self):
  with tempfile.TemporaryDirectory() as td:
   u='https://www.electrolux.co.uk/pdf';t,api=self.transport({u:(301,{'location':'https://evil.test/pdf'})},Path(td)/'log.json')
   with self.assertRaises(Exception):t.get(u)
   self.assertEqual(api.calls,[u])
 def test_explicit_no_redirect_preserved(self):
  with tempfile.TemporaryDirectory() as td:
   u='https://www.electrolux.co.uk/pdf';t,api=self.transport({u:(301,{'location':'/next'})},Path(td)/'log.json');r=t.get(u,allow_redirects=False);self.assertEqual(r.status_code,301);self.assertEqual(api.calls,[u])
 def test_active_target_stop_before_request(self):
  from product_tool.adapters.access_stop import stop_event,RATE_LIMIT
  from product_tool.adapters.policy_fetch import append_log_entry
  with tempfile.TemporaryDirectory() as td:
   log=Path(td)/'log.json';append_log_entry(log,stop_event('support.electroluxgroup.eu',RATE_LIMIT));u='https://www.electrolux.co.uk/pdf';t,api=self.transport({u:(301,{'location':'https://support.electroluxgroup.eu/pdf'})},log)
   with self.assertRaises(Exception):t.get(u)
   self.assertEqual(api.calls,[u])
 def test_redirect_loop_is_bounded(self):
  with tempfile.TemporaryDirectory() as td:
   u='https://www.electrolux.co.uk/pdf';t,api=self.transport({u:(301,{'location':u})},Path(td)/'log.json')
   with self.assertRaises(Exception):t.get(u)
   self.assertEqual(len(api.calls),6)
if __name__=='__main__':unittest.main()
