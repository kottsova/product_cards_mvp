from pathlib import Path
import json,hashlib
from product_tool.adapters.jbl import parse_pdp,queries
r=Path('reports/jbl_stage62');d=json.loads((r/'release_pass.json').read_text(encoding='utf-8'));b=d['baseline'];data=(r/'jbl_captures/JBLFLIP6BLKEU_attended.html')
if not data.exists():
 manifest=json.loads((r/'jbl_captures/JBLFLIP6BLKEU.manifest.json').read_text(encoding='utf-8')); data=r/'jbl_captures'/manifest['records'][0]['file']
html=data.read_text(encoding='utf-8');url=b['sources'][0]['url'];cases=[]
for sku in ['JBLFLIP6BLKEU','JBLFLIP6BLU','JBLFLIP6BLK','JBLFLIP6BLKEP']:
 doc,report=parse_pdp(html,url,sku);cases.append({'requested':sku,'returned_source':url,'match_level':doc.match_level,'identity':report['identity'],'confirmed_raw_specs':len(doc.attributes) if doc.match_level=='full_sku' else 0,'accepted':doc.match_level=='full_sku'})
family='<html><h1>JBL Flip 6</h1><p>Support, downloads and setup</p></html>';doc,report=parse_pdp(family,'https://support.jbl.com/gb/en/speakers/FLIP-6-.html','JBLFLIP6BLKEU');cases.append({'scenario':'family support only','match_level':doc.match_level,'identity':report['identity'],'accepted':doc.match_level=='full_sku','confirmed_raw_specs':0})
assert [x['accepted'] for x in cases]==[True,False,False,False,False]
(r/'identity_manual_review.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2),encoding='utf-8')
audit={'dataset_sha256':hashlib.sha256((r/'dataset_frozen.json').read_bytes()).hexdigest(),'baseline_before':json.loads((r/'baseline_before.json').read_text(encoding='utf-8')),'baseline_after':b,'models':d['results'],'baseline_queries':queries('JBLFLIP6BLKEU','JBL Flip 6'),'identity_review':cases,'dataset_counts':{'models':10,'exact_identity':sum(x['readiness']['exact_identity'] for x in d['results']),'raw_specs':sum(len(x['facts']) for x in d['results']),'confirmed_normalized_specs':sum(x['readiness']['confirmed_specs'] for x in d['results']),'ready':sum(x['readiness']['verdict']=='export_ready' for x in d['results']),'with_gaps':sum(x['readiness']['verdict']=='export_ready_with_gaps' for x in d['results']),'not_ready':sum(x['readiness']['verdict']=='not_ready' for x in d['results'])}}
(r/'before_after.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8');print(audit['dataset_counts']);print([(x['requested'] if 'requested' in x else x['scenario'],x['match_level']) for x in cases])
