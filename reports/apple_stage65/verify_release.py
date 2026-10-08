from pathlib import Path
import json,hashlib
from product_tool.apple_identity import parse_model
r=Path('reports/apple_stage65');x=json.loads((r/'final_acceptance.json').read_text(encoding='utf-8'));before=json.loads(Path('reports/apple_stage64/final_acceptance.json').read_text(encoding='utf-8'));rows=[]
for row in [x['baseline'],*x['results']]:
 ev=row['evidence'];m=ev['model_evidence'];path=r/'apple_captures'/(hashlib.sha256(m['url'].encode()).hexdigest()+'.html');doc,a=parse_model(path.read_text(encoding='utf-8'),m['url'],ev['model_key'],ev['configuration_fields']);assert a['admitted']==m['admitted'];assert all(not f['conflict'] for f in row['resolved']);assert row['readiness']['verdict']=='export_ready'
 rows.append(dict(article=row['article'],model_identity=ev['model_name'],configuration_identity=ev['identity']['configuration'],configuration_fields=ev['configuration_fields'],model_specs=row['readiness']['model_specs'],config_source_specs=sum(bool(f['full_sku_confirmed']) for f in row['resolved']),photos=sum(bool(p['selected']) for p in row['photos']),manual=ev['manual_status'],before=next((a['readiness']['verdict'] for a in before['results'] if a['article']==row['article']),'export_ready'),after=row['readiness']['verdict']))
photos=json.loads((r/'photo_inspection.json').read_text(encoding='utf-8'));assert len(photos)==27
for p in photos:assert hashlib.sha256((r/p['file']).read_bytes()).hexdigest()==p['sha256']
manifest=[dict(file=p.relative_to(r).as_posix(),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in (r/'apple_captures').iterdir() if p.suffix in {'.html','.pdf'}]
proof=dict(dataset_sha256=x['dataset_sha256'],model_parser_replays=len(rows),verified_photo_files=len(photos),captures=manifest,photo_candidates=sum(len(a['evidence'].get('photo_candidates',[])) for a in [x['baseline'],*x['results']]),rows=rows)
(r/'release_verification.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf-8');print('Verified 11 model replays and 27 image hashes; candidates',proof['photo_candidates'])
