from pathlib import Path
import json
from product_tool.adapters.jbl import parse_pdp
r=Path('reports/jbl_stage63');html=(r/'tune_1.html').read_text(encoding='utf-8');url='https://id.jbl.com/en/over-ear-headphones/JBLT520BTBLK.html';cases=[]
for code in ['JBLT520BTBLKEU','JBLT520BTWHTEU','JBLT520BTBLKEP','JBLT530BTBLKEU']:
 d,e=parse_pdp(html,url,code);cases.append({'scenario':'real black PDP re-evaluated for requested code','requested':code,'source_url':url,'model_identity':e['identity']['model_relation'],'variant_identity':e['identity']['variant_relation'],'full_sku':e['identity']['exact_sku'],'specs':len(d.attributes),'confirmed_photo_assets':e['exact_photo_assets']})
false=html.replace('01.JBL_Tune_520BT_ProductImage_Hero_Black.png','01.JBL_Tune_520BT_ProductImage_Hero_White.png');d,e=parse_pdp(false,url,'JBLT520BTBLKEU');cases.append({'scenario':'synthetic wrong-color hero in real PDP template','model_identity':e['identity']['model_relation'],'confirmed_photo_assets':e['exact_photo_assets']});assert not e['exact_photo_assets']
d,e=parse_pdp('<h1>JBL Tune 520BT</h1><p>Family support and downloads</p>','https://support.jbl.com/gb/en/tune520.html','JBLT520BTBLKEU');cases.append({'scenario':'synthetic family-only support','model_identity':e['identity']['model_relation'],'specs':len(d.attributes),'confirmed_photo_assets':e['exact_photo_assets']});assert not d.attributes
assert cases[0]['specs'] and cases[0]['confirmed_photo_assets'] and not cases[0]['full_sku'];assert cases[1]['specs'] and not cases[1]['confirmed_photo_assets'];assert cases[2]['specs'] and cases[2]['confirmed_photo_assets'];assert cases[3]['specs']==0
(r/'identity_manual_review.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2),encoding='utf-8');print('6 identity review scenarios verified')
s=Path('reports/jbl_stage62/restore_manual_proofs.py').read_text(encoding='utf-8').replace('jbl_stage62','jbl_stage63');(r/'restore_manual_proofs.py').write_text(s,encoding='utf-8')
