import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from product_tool import jobs
root=Path(__file__).resolve().parents[2];out=Path(__file__).parent;db=root/'data/batches.sqlite3'
frozen=json.loads((root/'reports/cross_brand_stage81/dataset.json').read_text(encoding='utf8'))['rows']
rows=[];provenance=[]
for pid in (101,109,92):
 p=jobs.get_product(db,pid);primary=p.get('input_search_code',p['search_code'])
 color=json.loads(p['identity_json']).get('variant_attributes',{}).get('color','')
 rows.append([p['category'],p['brand'],p['name'],primary,p['alternate_code'],color]);provenance.append(dict(source='current_user_product',id=pid))
for fid in (7,78,92):
 p=next(x for x in frozen if x['id']==fid)
 proof=root/'reports/cross_brand_stage81/qualified_live'/str(fid)/'result.json'
 good=json.loads(proof.read_text(encoding='utf8'));assert good['readiness']['verdict']=='export_ready'
 rows.append([p['category'],p['dispatch_brand'],p['name'],p['article'],'',p['input_color']]);provenance.append(dict(source='unchanged_Stage81_known_good_input',id=fid,previous_UI_policy_readiness=good.get('readiness_with_documents',{}).get('verdict')))
payload=dict(headers=['Категория','Бренд','Название','Артикул','Модель','Цвет'],rows=rows,provenance=provenance)
(out/'cross_inputs.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf8');print([(r[1],r[3],r[4]) for r in rows])
