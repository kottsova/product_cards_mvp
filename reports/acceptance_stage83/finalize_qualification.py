"""Fail closed: qualification cannot pass before actual live/parity/export/full tests."""
import sys,json,subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from product_tool.runtime_diagnostics import runtime_identity
out=Path(__file__).parent
read=lambda name:json.loads((out/name).read_text(encoding='utf8'))
reg=read('final_regression.json');assert reg['exit_code']==0 and reg['production_tree_unchanged']
parity=read('production_parity_release.json');assert parity['passed'] and len(parity['rows'])==6
ui=read('cross_brand_release/summary.json');direct=read('direct_release_shared_history/summary.json')
assert len(ui)==len(direct)==6 and all(r['job']=='done' and r['readiness']=='export_ready' for r in ui+direct)
export=read('export_qa.json');assert export['duplicate_product_columns']==0 and not export['formula_errors'] and export['raw_children_preserved']==38
qa=read('ui_qa.json');assert qa['compatibility_group'] and qa['actual_gallery_image_loaded'] and qa['lg_export_ready']
fingerprint=runtime_identity()['source_fingerprint']
for pid in [r['id'] for r in ui]:
 for phase in ('cross_brand_release','direct_release_shared_history'):
  data=read(f'{phase}/{pid}.json');assert data['runtime']['source_fingerprint']==fingerprint
subprocess.run(['git','diff','--check'],check=True)
subprocess.run(['git','diff','--cached','--check'],check=True)
subprocess.run(['git','diff','HEAD','--exit-code','--','reports/cross_brand_stage81/dataset.json'],check=True)
result=dict(verdict='Stage 83 PASS',live_UI=ui,live_direct=direct,parity='6/6; dispatch/providers/identity/facts/canonical/semantic evidence/readiness equal',source_fingerprint=fingerprint,regression=reg,export={k:export[k] for k in ('sha256','duplicate_product_columns','formula_errors','raw_children_preserved','raw_blocks')},UI=qa,thresholds='unchanged',frozen_dataset='unchanged',limitations=['Other seven current Apple batch rows were not processed by this acceptance run','Unknown/ambiguous compound descriptions remain intact','Empty DB without historical exact-article manual gives LG S3WER export_ready_with_gaps under normal UI policy; preserved separately'])
(out/'qualification_final.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
report=out/'README.md';text=report.read_text(encoding='utf8')
text=text.replace('Qualification verdict: live acceptance and UI/direct parity PASS; final Stage 83 PASS is conditional on the full regression result recorded beside this report.','Qualification verdict: **Stage 83 PASS**. Live acceptance, release UI/direct parity, UI/Excel raw preservation/localization and the complete final regression pass. See `qualification_final.json` and `final_regression.json` for machine-readable evidence.')
text+='\nFinal complete regression: '+ '; '.join(reg['summary'])+'. Production source tree unchanged during the suite: true.\n'
report.write_text(text,encoding='utf8')
print(json.dumps(dict(verdict=result['verdict'],regression=reg,source_fingerprint=fingerprint),ensure_ascii=False),flush=True)
