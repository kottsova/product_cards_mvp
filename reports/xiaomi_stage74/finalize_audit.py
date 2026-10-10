"""Finalize audit only after the immutable-source full regression actually passes."""
from pathlib import Path
import hashlib,json,subprocess
R=Path(__file__).parent
reg=json.loads((R/'regression_release.json').read_text(encoding='utf8'))
assert reg['exit_code']==0 and reg['source_tree_unchanged'] and 'OK' in reg['result']
qa=json.loads((R/'verification.json').read_text(encoding='utf8'))
assert qa['actual_live_models']==10 and qa['repeated_live_models']==5
assert qa['false_confirmed_configuration']==qa['duplicates']==qa['confirmed_retail_skus']==qa['ready']==0
assert hashlib.sha256((R/'dataset.json').read_bytes()).hexdigest()==(R/'dataset.sha256').read_text().strip()
subprocess.run(['git','diff','--check'],check=True)
p=R/'REPORT.md';text=p.read_text(encoding='utf8')
text=text.replace('**Audit verdict: PASS при успешном финальном regression. Adapter verdict: Xiaomi adapter not ready.**','**Audit verdict: PASS. Adapter verdict: Xiaomi adapter not ready.**')
text=text.replace('финальный статус дополняется после завершения.',f"Финальный результат: **{' / '.join(reg['result'])}**, source tree unchanged; elapsed {reg['elapsed_seconds']:.3f}s.")
p.write_text(text,encoding='utf8')
audit={'stage':74,'audit_verdict':'PASS','adapter_verdict':'Xiaomi adapter not ready','production_ready':False,'regression':{k:v for k,v in reg.items() if k!='source_manifest'},'live_models':qa['actual_live_models'],'repeated_live_models':qa['repeated_live_models'],'live_specs':qa['actual_live_specs'],'false_confirmed_configuration':0,'duplicates':0,'frozen_sha256':(R/'dataset.sha256').read_text().strip(),'known_limitations':['No confirmed appearance gallery.','Four partial phone configurations; no bound dynamic regional retail payload.','X20 Max PDF size cap; A27Qi image-only guide classifier false-negative.','Incomplete actual vacuum runtime mode extraction.','Frozen category labels damaged at creation; category presentation QA limited.'],'runtime_files_excluded':['SQLite databases','Python caches','browser profiles','data/node_modules'],'source_captures_are_public':True}
(R/'audit_verdict.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf8')
files=[p for p in R.rglob('*') if p.is_file() and p.name!='evidence_manifest.json' and p.suffix in {'.py','.json','.jsonl','.html','.pdf','.gz','.png','.xlsx','.sha256','.md','.log'} and '__pycache__' not in p.parts]
manifest={str(p.relative_to(R)).replace('\\','/'):{'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size} for p in sorted(files)}
(R/'evidence_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
print('Stage 74 audit PASS; adapter NOT READY; public evidence files',len(files))
