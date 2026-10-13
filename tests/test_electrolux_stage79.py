"""Revision inventory is existence evidence; live qualification is separate."""
import hashlib,json,tempfile,unittest
from pathlib import Path
from bs4 import BeautifulSoup
from product_tool.electrolux_page import parse,inventory,official,components,revision_owner,media_asset
from product_tool.adapters.electrolux import ElectroluxAdapter
from tests.test_electrolux_stage78 import native,changed,URL
R=Path(__file__).resolve().parents[1]/'reports/electrolux_stage79'
EOD='https://www.electrolux.co.uk/kitchen/cooking/ovens/oven/eod6c46k2/'
IE='https://www.electrolux.ie/laundry/laundry/washing-machines/front-loader-washing-machine/efi61141b/'
SHOP='https://shop.electrolux.co.uk/model/m/EOD6C46K2'
def fixture(url):return (R/(hashlib.sha256(url.encode()).hexdigest()[:12]+'.html')).read_text(encoding='utf8')
class ElectroluxStage79(unittest.TestCase):
 def test_published_inventory_retains_both_revisions(self):
  ev=inventory(fixture(SHOP),SHOP,'EOD6C46K2','94949957800');self.assertEqual([r['pnc'] for r in ev['relations']],['94949957800','94949957801']);self.assertEqual(ev['requested_relation'],'published_exact_revision');self.assertFalse(ev['technical_equivalence'])
 def test_unknown_revision_not_selected(self):
  ev=inventory(fixture(SHOP),SHOP,'EOD6C46K2','94949957899');self.assertEqual(ev['requested_relation'],'not_in_published_inventory');self.assertNotIn('selected_pnc',ev)
 def test_wrong_model_inventory(self):self.assertEqual(inventory(fixture(SHOP),SHOP,'EOD6C46K')['relations'],[])
 def test_inventory_ignores_numeric_buttons_without_owner(self):self.assertEqual(inventory('<button role="menuitem" aria-label="94949957800"></button>',SHOP,'EOD6C46K2')['relations'],[])
 def test_menu_payload_disagreement(self):
  s=BeautifulSoup(fixture(SHOP),'html.parser');s.select_one('button[aria-label="94949957801"]').decompose();self.assertEqual(inventory(str(s),SHOP,'EOD6C46K2')['relations'],[])
 def test_foreign_inventory_rejected(self):self.assertEqual(inventory(fixture(SHOP),'https://electrolux.co.uk.evil.test/model/m/EOD6C46K2','EOD6C46K2')['relations'],[])
 def test_revision_inventory_does_not_upgrade_pdp(self):
  doc,ev=parse(fixture(EOD),EOD,'EOD6C46K2','94949957800','UK');ev['pnc_inventory']=inventory(fixture(SHOP),SHOP,'EOD6C46K2','94949957800');self.assertFalse(ev['identity']['configuration_confirmed']);self.assertEqual(len(doc.attributes),1);self.assertFalse(any(p['eligible'] for p in ev['gallery_inventory']));self.assertGreater(len(ev['rejected_facts']),30)
 def test_base_pdp_extraction_is_complete(self):
  doc,ev=parse(fixture(EOD),EOD,'EOD6C46K2','949499578','UK');self.assertGreater(len(doc.attributes),30);self.assertGreater(len(ev['gallery_inventory']),2);self.assertTrue(all(p['eligible'] for p in ev['gallery_inventory']));self.assertEqual(ev['identity']['published_finish'],'Black')
 def test_ie_is_official_but_region_relation_still_required(self):
  self.assertTrue(official(IE));doc,ev=parse(fixture(IE),IE,'EFI61141B','','UK');self.assertFalse(ev['identity']['configuration_confirmed']);self.assertEqual(ev['identity']['region'],'IE');self.assertFalse(any(p['eligible'] for p in ev['gallery_inventory']))
 def test_same_pnc_regional_catalog_route_holds_sensitive_facts(self):
  relation={'model':'EFI61141B','product_code':'914932044','region':'UK','source_url':'https://www.electrolux.co.uk/laundry/laundry/washing-machines/','source_type':'native_catalog_productData'}
  doc,ev=parse(fixture(IE),IE,'EFI61141B','','UK','',[relation]);self.assertTrue(ev['identity']['configuration_confirmed']);self.assertGreater(len(doc.attributes),10);self.assertFalse(any(f.name=='Напряжение питания, В' for f in doc.attributes));self.assertTrue(any(r['reason'].startswith('Regional electrical') for r in ev['rejected_facts']));self.assertFalse(any(d['identity_verified'] for d in ev['document_inventory'] if d['type']=='Energy Label'))
 def test_catalog_bridge_never_overrides_exact_input_pnc(self):
  relation={'model':'EFI61141B','product_code':'914932044','region':'UK','source_url':'https://www.electrolux.co.uk/','source_type':'native_catalog_productData'}
  _,ev=parse(fixture(IE),IE,'EFI61141B','91493204400','UK','',[relation]);self.assertFalse(ev['identity']['configuration_confirmed'])
 def test_duplicate_label_values_are_preserved(self):
  _,ev=parse(fixture(IE),IE,'EFI61141B','','IE');c=next(c for c in ev['source_field_collisions'] if c['label']=='Push Button Functions');self.assertEqual(c['classification'],'same_owner_duplicate_label_different_values');self.assertEqual(len(c['rows']),2);self.assertNotEqual(c['rows'][0]['value'],c['rows'][1]['value'])
 def test_exact_pnc_candidate_not_first_model(self):
  def edit(d):
   owner=next(c for c in components(d) if c.get('name')=='PDPContainer');owner['props']['productCode']='944032052';next(c for c in components(owner) if c.get('name')=='TopArea')['props']['productCode']='944032052'
  pages={'https://www.electrolux.co.uk/':('<a href="/a/EOF6P46X/">model</a><a href="/b/EOF6P46X/">model</a>','https://www.electrolux.co.uk/'),'https://www.electrolux.co.uk/a/EOF6P46X/':(native(),'https://www.electrolux.co.uk/a/EOF6P46X/'),'https://www.electrolux.co.uk/b/EOF6P46X/':(changed(edit),'https://www.electrolux.co.uk/b/EOF6P46X/')}
  class Fake(ElectroluxAdapter):
   def fetch(self,url,**kw):return pages.get(url)
   def find_inventory(self,*args):return {'relations':[]}
  with tempfile.TemporaryDirectory() as t:
   a=Fake(clock=lambda:0,fetch_log_path=Path(t)/'log.json');doc=a.find_source('944032052',name='Electrolux EOF6P46X',region='UK',deadline=100);self.assertEqual(a.reports['944032052']['identity']['product_code'],'944032052');self.assertEqual(doc.match_level,'full_sku')
 def test_ireland_gallery_bytes_and_type(self):
  from io import BytesIO
  from PIL import Image
  import requests
  from product_tool.photo_metadata import inspect_saved_photo
  im=Image.new('RGB',(500,400),'white');im.putpixel((0,0),(0,0,0));buf=BytesIO();im.save(buf,format='PNG');raw=buf.getvalue()
  class Transport:
   headers={}
   def get(self,url,**kw):
    r=requests.Response();r.status_code=200;r.url=url;r.headers['Content-Type']='image/png';r._content=raw;r._content_consumed=True;return r
  with tempfile.TemporaryDirectory() as t:
   m=inspect_saved_photo('https://www.electrolux.ie/services/eml/model.png','electrolux',Path(t)/'log.json',underlying=Transport());self.assertEqual((m['width'],m['height']),(500,400));self.assertEqual(m['sha256'],hashlib.sha256(raw).hexdigest());self.assertEqual(m['content_type'],'image/png')
 def test_lookalike_ireland_image_host_rejected(self):
  from product_tool.photo_metadata import inspect_saved_photo
  with tempfile.TemporaryDirectory() as t:
   with self.assertRaisesRegex(ValueError,'not approved'):inspect_saved_photo('https://electrolux.ie.evil.test/p.png','electrolux',Path(t)/'log.json')
 def test_exact_revision_owner_has_only_identity_and_gallery(self):
  record=json.loads((R/'revision_route_research.json').read_text(encoding='utf8'))[0];html=(R/record['file']).read_text(encoding='utf8');ev=revision_owner(html,record['url'],'EOD6C46K2','94949957800');self.assertTrue(ev['confirmed']);self.assertEqual(ev['revision'],'00');self.assertEqual(len(ev['gallery']),1);self.assertFalse(ev['technical_equivalence']);self.assertNotIn('attributes',ev);self.assertNotIn('documents',ev)
 def test_revision_owner_never_selects_sibling(self):
  record=json.loads((R/'revision_route_research.json').read_text(encoding='utf8'))[0];html=(R/record['file']).read_text(encoding='utf8');self.assertFalse(revision_owner(html,record['url'],'EOD6C46K2','94949957801')['confirmed']);self.assertFalse(revision_owner(html,record['url'],'EOD6C46K','94949957800')['confirmed'])
 def test_revision_owner_rejects_foreign_source(self):
  record=json.loads((R/'revision_route_research.json').read_text(encoding='utf8'))[0];html=(R/record['file']).read_text(encoding='utf8');self.assertFalse(revision_owner(html,'https://evil.test/search?pnc=94949957800','EOD6C46K2','94949957800')['confirmed'])
 def test_base_specs_stay_partial_after_revision_identity(self):
  record=json.loads((R/'revision_route_research.json').read_text(encoding='utf8'))[0];html=(R/record['file']).read_text(encoding='utf8');revision=revision_owner(html,record['url'],'EOD6C46K2','94949957800');doc,ev=parse(fixture(EOD),EOD,'EOD6C46K2','94949957800','UK');ev['requested_revision']=revision;self.assertTrue(revision['confirmed']);self.assertEqual(len(doc.attributes),1);self.assertFalse(ev['identity']['configuration_confirmed'])
 def test_published_derivative_same_asset(self):
  record=json.loads((R/'revision_route_research.json').read_text(encoding='utf8'))[0];html=(R/record['file']).read_text(encoding='utf8');revision=revision_owner(html,record['url'],'EOD6C46K2','94949957800');_,ev=parse(fixture(EOD),EOD,'EOD6C46K2','94949957800','UK');self.assertEqual(media_asset(revision['gallery'][0]['url']),media_asset(ev['gallery_inventory'][0]['url']))
 def test_crop_query_and_different_file_not_equivalent(self):
  a='https://electrolux.bynder.com/transform/WS_PV/8f908c48-172e-460c-897a-6de15fa11cf3/2023889108-eps';self.assertIsNone(media_asset(a+'?crop=1'));self.assertNotEqual(media_asset(a),media_asset(a.replace('2023889108-eps','other-eps')));self.assertIsNone(media_asset(a.replace('electrolux.bynder.com','evil.test')))
