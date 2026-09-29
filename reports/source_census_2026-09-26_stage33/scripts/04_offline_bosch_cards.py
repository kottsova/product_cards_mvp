"""Offline parse of the two saved Bosch pages and the one saved document."""
from __future__ import annotations
import gzip,json,re,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];STAGE=HERE.parent
sys.path.insert(0,str(ROOT))
from product_tool.adapters.structured_page import extract_json_ld_product
from product_tool.offline_guard import offline_only
IDENTITY={'name','sku','productID','gtin','gtin8','gtin12','gtin13','gtin14','mpn'}
def main():
 with offline_only():
  d=json.loads((STAGE/'raw/bosch_route_declaration.json').read_text(encoding='utf-8'))
  index=[json.loads(x) for x in (STAGE/'bosch_route/responses/index.jsonl').read_text(encoding='utf-8').splitlines()]
  manual=json.loads((STAGE/'raw/bosch_manual_result.json').read_text(encoding='utf-8'))
  out=[]
  for sku,route in d['first_batch'].items():
   entry=next(x for x in index if x['url']==route['url'])
   with gzip.open(STAGE/'bosch_route/responses'/entry['saved_as'],'rt',encoding='utf-8') as h:html=h.read()
   fields=extract_json_ld_product(html,route['url'])
   identity={f.name:f.value for f in fields if f.name in IDENTITY}
   specs=[{'name':f.name,'value':f.value,'source_url':route['url']} for f in fields if f.name not in IDENTITY|{'json_ld_image'}]
   images=list(dict.fromkeys(f.value for f in fields if f.name=='json_ld_image'))
   tied=[u for u in images if re.search(re.escape(sku)+r'(?![A-Z0-9])',u,re.I)]
   other=[u for u in images if u not in tied]
   decoded=html.replace('\\"','"')
   documents=[{'type':kind,'url':url} for kind,url in re.findall(r'"titleKey":"([^"]+)".{0,250}?"url":"(https://media3\.bsh-group\.com/Documents/[^" ]+?\.pdf)"',decoded)]
   e_numbers=sorted(set(re.findall(re.escape(sku)+r'/\d{2}',html,re.I)))
   status='full_model_code_on_other_market_page_variant_open' if identity.get('mpn')==sku and not e_numbers else 'identity_review'
   record={'category':'Блендеры' if sku=='MMB2111M' else 'Чайники электрические','article':sku,'catalog_market_variant':'not confirmed by the observed other-market page','page_market':route['market'],'page_url':route['url'],'page_identity':identity,'e_number_revisions_in_page':e_numbers,'model_status':status,'specifications_on_observed_page':specs,'photos_on_observed_page':{'total':len(images),'code_tied':tied,'other_variant_or_generic':other},'documents_on_observed_page':documents,'instruction_status':'not found on this checked page; no global absence conclusion' if sku=='MMB2111M' else 'full multilingual instruction with Russian operating section, official page link, family code TWK720. in file; exact TWK7203 absent from file; market variant unverified','instruction_assessment':manual['assessment'] if sku=='TWK7203' else None,'card_readiness':'not_ready','card_gaps':['market_variant_not_confirmed','production_adapter_not_available']+(['full_russian_instruction_not_found_on_checked_page'] if sku=='MMB2111M' else ['manual_file_does_not_name_exact_code'])}
   assert identity.get('mpn')==sku and len(specs)>=20 and len(tied)>=4
   assert not e_numbers
   out.append(record)
  assert len(out)==2 and out[0]['article']=='MMB2111M' and out[1]['article']=='TWK7203'
  assert len(out[0]['specifications_on_observed_page'])==22 and len(out[0]['photos_on_observed_page']['code_tied'])==28
  assert len(out[1]['specifications_on_observed_page'])==29 and len(out[1]['photos_on_observed_page']['code_tied'])==4
  assert any(x['type']=='user-manuals' and x['url']==manual['url'] for x in out[1]['documents_on_observed_page'])
  (STAGE/'raw/bosch_two_result.json').write_text(json.dumps({'cards':out},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
  print(json.dumps({'cards':[{'article':x['article'],'mpn':x['page_identity'].get('mpn'),'market':x['page_market'],'specs':len(x['specifications_on_observed_page']),'photos_code_tied':len(x['photos_on_observed_page']['code_tied']),'photos_other':len(x['photos_on_observed_page']['other_variant_or_generic']),'documents':[(y['type'],y['url']) for y in x['documents_on_observed_page']],'instruction_status':x['instruction_status'],'card_readiness':x['card_readiness']} for x in out]},ensure_ascii=True,indent=2))
if __name__=='__main__':main()
