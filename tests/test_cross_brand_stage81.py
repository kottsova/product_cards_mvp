"""Semantic regression for Stage 81; all network traffic is offline guarded."""
import unittest,tempfile,json
from pathlib import Path
from unittest.mock import patch
from product_tool import attribute_projection,canonical_attributes,normalization,jobs,storage,card_evidence,readiness,photo_inventory
from product_tool.adapters.common import RawAttribute,SourceDocument,PhotoCandidate

class Stage81Regression(unittest.TestCase):
 def test_same_axis_aliases_merge_with_all_parents_and_real_conflict(self):
  def row(source,value,parent):
   fact={'source_key':source,'normalized_name':parent,'normalized_value':value,'unit':'mm','raw_name':parent,'raw_value':value,'section':'Dimensions'}
   return {'normalized_name':'package_w_mm','derived_from':parent,'raw_names':[parent],'sources':{source:fact},'resolved':{'selected_value':value,'selected_unit':'mm','selected_source':source,'status':'full_sku_lg','conflict':False},'display_name':'Ширина упаковки, мм'}
  pages=[{'source_key':key,'match_level':'full_sku','error':''} for key in ('lg_ru','lg_kz')]
  data=[row('lg_ru','540','alias_ru'),row('lg_kz','540','alias_kz')]
  merged=attribute_projection.merge_dimension_aliases(data,pages)
  self.assertEqual(1,len(merged));self.assertFalse(merged[0]['resolved']['conflict']);self.assertEqual({'alias_ru','alias_kz'},set(merged[0]['derived_from_names']))
  data[1]=row('lg_kz','628','alias_kz');merged=attribute_projection.merge_dimension_aliases(data,pages)
  self.assertTrue(merged[0]['resolved']['conflict']);self.assertFalse(merged[0]['resolved']['full_sku_confirmed']);self.assertEqual({'lg_ru','lg_kz'},set(merged[0]['sources']))
 def test_animated_gif_bytes_are_lossless_and_blank_first_frame_is_not_placeholder(self):
  from PIL import Image
  from io import BytesIO
  import requests,hashlib
  from product_tool.photo_metadata import inspect_saved_photo
  first=Image.new('RGB',(128,128),'white');second=first.copy();second.paste('black',(32,32,96,96))
  output=BytesIO();first.save(output,format='GIF',save_all=True,append_images=[second],duration=100,loop=0);data=output.getvalue()
  class Session:
   headers={}
   def get(self,url,**kwargs):
    response=requests.Response();response.url=url;response.status_code=200;response.headers['content-type']='image/gif';response._content=data;response._content_consumed=True;response.encoding='utf-8';return response
  with tempfile.TemporaryDirectory() as folder:
   result=inspect_saved_photo('https://www.lg.com/model.gif','lg_ru',Path(folder)/'log.json',underlying=Session(),full_verification=True)
  self.assertEqual(('GIF',128,128),(result['format'],result['width'],result['height']));self.assertEqual(hashlib.sha256(data).hexdigest(),result['sha256'])
 def test_imperial_duplicate_requires_numeric_equivalence(self):
  from product_tool.jbl_presentation import project
  def row(name,value,key):return {'normalized_name':key,'raw_names':[name],'sources':{'jbl':{'raw_name':name,'raw_value':value}},'resolved':{'display_value':value,'selected_value':value,'selected_unit':'','conflict':False,'full_sku_confirmed':True,'status':'full_sku_official'}}
  result=project([row('Net Weight (kgs)','2.1','kg'),row('Net Weight (lbs)','4.63','lbs')])
  self.assertEqual(1,len(result));self.assertFalse(result[0].get('source_unit_conflict'))
  result=project([row('Berat earpiece (g)','10.8','g'),row('Berat earpiece (oz)','0.3','oz')])
  self.assertEqual(1,len(result));self.assertTrue(result[0]['source_unit_conflict']);self.assertTrue(result[0]['resolved']['conflict']);self.assertFalse(result[0]['resolved']['full_sku_confirmed'])
  self.assertEqual('oz',result[0]['refined_from']);self.assertIn('унции',result[0]['resolved']['display_value'])
 def test_no_manual_refresh_preserves_scoped_previous_document_evidence(self):
  with tempfile.TemporaryDirectory() as folder:
   db=Path(folder)/'x.sqlite3';jobs.initialize(db)
   with storage._connection(db) as c:
    c.execute("INSERT INTO batches VALUES ('b','x','x','{}','x')")
    pid=c.execute("INSERT INTO products (batch_id,row_number,name,brand,search_code,alternate_code,category,needs_confirmation,issues_json,original_values_json) VALUES ('b',1,'Old','Xiaomi','Old','','Test',0,'[]','{}')").lastrowid
   old={'identity':{'model':'Old'},'manuals':[{'url':'https://example.org/old.pdf'}],'verified_documents':['https://example.org/old.pdf'],'manual_status':'Проверена'}
   card_evidence.save(db,pid,'xiaomi',old)
   fresh={'identity':{'model':'New'},'verified_documents':[],'manual_status':'Не проверена'}
   card_evidence.save(db,pid,'xiaomi',fresh);card_evidence.save(db,pid,'xiaomi',fresh)
   result=card_evidence.load(db,pid,'xiaomi')
   self.assertEqual([],result['verified_documents']);self.assertEqual('Не проверена',result['manual_status'])
   self.assertEqual(1,len(result['retained_document_evidence']))
   self.assertEqual(old['identity'],result['retained_document_evidence'][0]['identity'])
   self.assertEqual(old['verified_documents'],result['retained_document_evidence'][0]['documents']['verified_documents'])
 def test_component_dimension_axes_do_not_overwrite_another_block(self):
  with tempfile.TemporaryDirectory() as folder:
   db=Path(folder)/'x.sqlite3';jobs.initialize(db)
   with storage._connection(db) as c:
    c.execute("INSERT INTO batches VALUES ('b','x','x','{}','x')")
    pid=c.execute("INSERT INTO products (batch_id,row_number,name,brand,search_code,alternate_code,category,needs_confirmation,issues_json,original_values_json) VALUES ('b',1,'AC','Samsung','TEST1234','','Сплит-системы',0,'[]','{}')").lastrowid
   doc=SourceDocument('samsung','Samsung','https://www.samsung.com/fixture/',found_model='TEST1234',match_level='full_sku',attributes=[RawAttribute('Размеры внутреннего блока (Ш x В x Г, мм)','100 x 200 x 300'),RawAttribute('Размеры наружного блока (Ш x В x Г, мм)','400 x 500 x 600')])
   jobs.save_source_document(db,pid,doc);jobs.resolve_product(db,pid)
   rows=attribute_projection.final_attribute_rows(db,pid)
   self.assertEqual(6,len(rows));self.assertEqual(6,len({x['normalized_name'] for x in rows}))
   self.assertEqual({'100 мм','200 мм','300 мм','400 мм','500 мм','600 мм'},{x['resolved']['display_value'] for x in rows})
 def test_packaging_axis_alias_uses_published_section_order(self):
  f=normalization.normalize_fact(RawAttribute('В упаковке','628 x 286 x 223','Габариты Г x Ш x В, мм',True))
  self.assertEqual('package_dimensions',f.normalized_name);self.assertEqual('w=286;h=223;d=628',f.normalized_value)
  f=normalization.normalize_fact(RawAttribute('Без упаковки','260 x 270 x 1120','Габариты Г x Ш x В, мм',True))
  self.assertEqual('product_dimensions',f.normalized_name);self.assertEqual('w=270;h=1120;d=260',f.normalized_value)
 def test_false_feature_is_kept_but_missing_quantity_is_not_false(self):
  feature=normalization.normalize_fact(RawAttribute('TurboWash','-','Функции',True));quantity=normalization.normalize_fact(RawAttribute('Объём пылесборника (л)','-','Характеристики',True))
  self.assertEqual(('false','bool'),(feature.normalized_value,feature.unit))
  self.assertEqual(('unknown','unknown'),(quantity.normalized_value,quantity.unit))
  row={'normalized_name':'turbowash','display_name':'TurboWash','sources':{'lg_ru':{'raw_name':'TurboWash','raw_value':'-','normalized_value':'false','unit':'bool'}},'raw_names':['TurboWash'],'resolved':{'selected_value':'false','selected_unit':'bool','selected_source':'lg_ru','display_value':'Нет','conflict':False}}
  self.assertEqual(1,len(attribute_projection.project_final_rows([row])))
 def test_input_color_does_not_become_official_color(self):
  product={'brand':'Xiaomi','search_code':'Xiaomi 15','name':'Xiaomi 15 [color=Black]'}
  color=canonical_attributes.color_result(product,[],[],{'requested_configuration':{'color':'Black'}})
  self.assertFalse(color['confirmed']);self.assertEqual('не подтверждён',color['value'])
 def test_rendition_dedupe_keeps_different_angles_and_color(self):
  base='https://id.jbl.com/on/demandware.static/-/Sites-masterCatalog_Harman/default/dw1/FRONT_BLACK.png'
  alias='https://id.jbl.com/dw/image/v2/AAUJ_PRD'+base.split('jbl.com')[1]+'?sw=537&sfrm=png'
  self.assertEqual(photo_inventory.normalized_asset(base),photo_inventory.normalized_asset(alias))
  self.assertNotEqual(photo_inventory.normalized_asset(base),photo_inventory.normalized_asset(base.replace('FRONT','BACK')))
  self.assertNotEqual(photo_inventory.normalized_asset(base),photo_inventory.normalized_asset(base.replace('BLACK','WHITE')))
 def test_verified_resize_aliases_dedupe_despite_different_sha(self):
  rows=[{'identity_confirmed':True,'official_color':'Black','variant_relation':'exact','normalized_asset':'front','sha256':'small'},
        {'identity_confirmed':True,'official_color':'Black','variant_relation':'exact','normalized_asset':'front','sha256':'large'},
        {'identity_confirmed':True,'official_color':'Black','variant_relation':'exact','normalized_asset':'back','sha256':'back'},
        {'identity_confirmed':False,'official_color':'Black','variant_relation':'exact','normalized_asset':'front','sha256':'large'}]
  groups=photo_inventory.dedupe_groups(rows)
  self.assertEqual([1,1,2],sorted(map(len,groups)))
 def test_only_manual_gaps_move_to_advisory_in_audit_scope(self):
  base={'verdict':'not_ready','blocking_gaps':['manual_unverified','model_missing'],'advisory_gaps':[],'gaps':['manual_unverified','model_missing']}
  with patch('product_tool.readiness._card_readiness',return_value=base):r=readiness.card_readiness(Path('unused'),1,manuals_required=False)
  self.assertEqual(['model_missing'],r['blocking_gaps']);self.assertEqual('not_ready',r['verdict']);self.assertEqual(['manual_unverified'],r['advisory_gaps'])
 def test_gallery_metadata_survives_photo_row_id_refresh(self):
  with tempfile.TemporaryDirectory() as folder:
   db=Path(folder)/'x.sqlite3';jobs.initialize(db)
   with storage._connection(db) as c:
    c.execute("INSERT INTO batches VALUES ('b','x','x','{}','x')")
    pid=c.execute("INSERT INTO products (batch_id,row_number,name,brand,search_code,alternate_code,category,needs_confirmation,issues_json,original_values_json) VALUES ('b',1,'TV','Samsung','TEST1234','','Телевизоры',0,'[]','{}')").lastrowid
   url='https://images.samsung.com/is/image/samsung/p6pim/kz_ru/test1234/gallery/front'
   doc=SourceDocument('samsung','Samsung','https://www.samsung.com/fixture/',found_model='TEST1234',match_level='full_sku',photo_candidates=[PhotoCandidate(url,'front')])
   jobs.save_source_document(db,pid,doc);card_evidence.save(db,pid,'samsung_page',{'photos':{'gallery':[url]}})
   p=jobs.get_photo_candidates(db,pid)[0];photo_inventory.persist_measurement(db,pid,p,{'width':800,'height':600,'size_bytes':10000,'format':'PNG','sha256':'a'*64})
   jobs.save_source_document(db,pid,SourceDocument('samsung_other','Samsung','https://www.samsung.com/other/',match_level='full_sku',photo_candidates=[PhotoCandidate(url+'/other','other')]))
   jobs.save_source_document(db,pid,doc)
   new=next(x for x in photo_inventory.enriched_photos(db,pid) if x['source_key']=='samsung')
   self.assertNotEqual(p['id'],new['id']);self.assertTrue(new['byte_verified']);self.assertEqual('a'*64,new['sha256'])
 def test_jbl_live_gallery_dom_not_limited_to_jsonld_hero(self):
  from product_tool.adapters.jbl import parse_pdp
  path=Path('reports/cross_brand_stage81/baseline_live/1/raw_sources/jbl.html')
  doc,evidence=parse_pdp(path.read_text(encoding='utf8'),'https://id.jbl.com/bluetooth-portables/JBLCHARGE5BLK.html','JBLCHARGE5BLK')
  self.assertTrue(evidence['identity']['model_confirmed'])
  photos=[p for p in doc.photo_candidates if p.kind=='product_gallery']
  self.assertGreaterEqual(len(photos),7);self.assertEqual(len(photos),len({p.url for p in photos}));self.assertFalse(any('.svg' in p.url for p in photos))
 def test_xiaomi_explicit_main_model_assets_are_model_photos(self):
  from product_tool.xiaomi_page import model_gallery
  html='<main><div><img class="xm-img" alt="Xiaomi Robot Vacuum X20 Plus" src="https://i02.appmifile.com/model/front.png"><img class="xm-img" alt="Xiaomi Robot Vacuum X20 Plus" data-src="https://i02.appmifile.com/model/back.png"><img class="xm-img" alt="Xiaomi Robot Vacuum X20 Max" src="https://i02.appmifile.com/other-model/front.png"></div></main>'
  photos,relations=model_gallery(html,'https://www.mi.com/global/product/xiaomi-robot-vacuum-x20-plus/','Xiaomi Robot Vacuum X20+')
  self.assertEqual(2,len(photos));self.assertTrue(all(r['model_relation']=='model_confirmed' and r['supplier_color_relation']=='unproven' for r in relations))
 def test_xiaomi_memory_technology_survives_capacity_candidate_section(self):
  from product_tool.xiaomi_page import parse_page
  path=Path('reports/cross_brand_stage81/baseline_live/78/raw_sources/xiaomi_model.html')
  doc,ev=parse_page(path.read_text(encoding='utf8'),'https://www.mi.com/global/product/xiaomi-15/specs/','Xiaomi 15','Xiaomi 15 [RAM=12GB]','Смартфоны')
  found={a.name:a.value for a in doc.attributes}
  self.assertIn('LPDDR5X',found['Тип оперативной памяти']);self.assertEqual('UFS 4.0',found['Тип накопителя'])
  self.assertTrue(any('Storage' in x['name'] and x['scope']=='configuration' for x in ev['configuration_candidates']))
  self.assertEqual(len(ev['raw_specs']),len(ev['accepted_specs'])+len(ev['rejected_specs']))
  self.assertFalse(any(a.name=='Объём накопителя' for a in doc.attributes))
 def test_redmi_mixed_fields_keep_common_axes_and_connectivity(self):
  from product_tool.xiaomi_page import parse_page
  path=Path('reports/cross_brand_stage81/baseline_live/87/raw_sources/xiaomi_model.html')
  doc,ev=parse_page(path.read_text(encoding='utf8'),'https://www.mi.com/global/product/redmi-note-14-pro-5g/specs/','Redmi Note 14 Pro 5G','Redmi Note 14 Pro 5G [color=Black]','Смартфоны')
  found={a.name:a.value for a in doc.attributes}
  self.assertEqual('162.33',found['Высота товара, мм']);self.assertEqual('74.42',found['Ширина товара, мм']);self.assertEqual('190',found['Вес товара, г'])
  self.assertFalse(any('толщин' in a.name.lower() for a in doc.attributes))
  self.assertIn('LPDDR4X',found['Тип оперативной памяти']);self.assertIn('UFS2.2',found['Тип накопителя'])
  self.assertIn('Bluetooth',found);self.assertIn('Wireless Networks',found);self.assertIn('Network bands',found)
  self.assertTrue(any(x['name']=='SIM' and x['scope']=='region' for x in ev['rejected_specs']))
 def test_watch_minimum_and_maximum_brightness_are_different_fields(self):
  from product_tool.apple_identity import parse_model
  path=Path('reports/cross_brand_stage81/final_live/45/raw_sources/apple_model.html')
  doc,ev=parse_model(path.read_text(encoding='utf8'),'https://support.apple.com/en-us/121202','watch10',{'case_size':'46'})
  brightness=[a for a in doc.attributes if 'Яркость' in a.name]
  self.assertEqual(2,len(brightness));self.assertEqual(2,len({a.name for a in brightness}))
  self.assertTrue(any('минимальная' in a.name and '1 nit' in a.value for a in brightness))

if __name__=='__main__':unittest.main()
