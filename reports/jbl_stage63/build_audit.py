from pathlib import Path
import json,hashlib
r=Path('reports/jbl_stage63');a=json.loads((r/'release_pass.json').read_text(encoding='utf-8'));b=json.loads(Path('reports/jbl_stage62/release_pass.json').read_text(encoding='utf-8'));before={x['article']:x for x in b['results']};out=[];assert len(a['results'])==10
for x in a['results']:
 e=x['evidence'];out.append({'sku':x['article'],'was':before[x['article']]['readiness'],'source_urls':[p['url'] for p in x['sources'] if p['source_key']=='jbl'],'identity':e['identity'],'specs':len(x['facts']),'confirmed_specs':x['readiness']['confirmed_specs'],'photos':len(e['exact_photo_assets']),'manual':x['readiness']['manual_status'],'now':x['readiness'],'variant_candidates':e['rejected_specs']})
 if not e['identity']['exact_sku']:assert all(not f['full_sku_confirmed'] for f in x['resolved'])
counts={'raw_specs':sum(x['specs'] for x in out),'confirmed_specs':sum(x['confirmed_specs'] for x in out),'model_confirmed':len(out),'ready':sum(x['now']['verdict']=='export_ready' for x in out),'full_sku':sum(x['now']['exact_sku_identity'] for x in out),'model_only':sum(not x['now']['exact_sku_identity'] for x in out)}
digest=hashlib.sha256(Path('reports/jbl_stage62/dataset_frozen.json').read_bytes()).hexdigest();assert digest=='b6cd9ed36c3920aa176c3ac7ed3cb47ce17660f0899db247dc059ebe833a2634'
result={'dataset_path':'reports/jbl_stage62/dataset_frozen.json','dataset_sha256':digest,'counts':counts,'models':out,'external_search':json.loads((r/'external_search_smoke.json').read_text(encoding='utf-8'))};(r/'before_after.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(counts)
