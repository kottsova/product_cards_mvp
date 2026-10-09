"""Stage only source changes and bounded public audit files, never browser state."""
from pathlib import Path
import os,json,subprocess,hashlib
R=Path(__file__).parent;root=Path.cwd().resolve();assert R.resolve().is_relative_to(root)
assert json.loads((R/'acceptance_summary.json').read_text(encoding='utf8'))['audit']=='PASS'
reg=json.loads((R/'regression_release.json').read_text(encoding='utf8'));assert reg['exit_code']==0 and reg['source_tree_unchanged']
now={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for directory in ('product_tool','tests') for p in Path(directory).rglob('*') if p.is_file() and p.suffix in {'.py','.js','.html'}}
assert now==reg['source_manifest'],'Source changed after full regression'
assert hashlib.sha256((R/'frozen_inputs.json').read_bytes()).hexdigest()==(R/'frozen_inputs.sha256').read_text().strip()
paths=[];skip={'node_modules','ui','__pycache__','attended_profile','attended_search'}
for directory,dirs,files in os.walk(R,followlinks=False):
 dirs[:]=[n for n in dirs if n not in skip and not os.path.islink(Path(directory)/n) and not os.path.isjunction(Path(directory)/n)]
 for name in files:
  p=Path(directory)/name
  if '.sqlite3' in name or name.endswith('.pyc'):continue
  if name.endswith('.log') and name!='regression_release.log':continue
  assert p.resolve().is_relative_to(root) and p.stat().st_size<90000000;paths.append(str(p.relative_to(root)))
changed=subprocess.check_output(['git','diff','--name-only'],text=True).splitlines()
assert not any(p.startswith('reports/') and not p.startswith('reports/razer_stage71/') for p in changed)
changed+=['product_tool/census/public_browser.py','product_tool/razer_store.py','tests/test_razer_stage71.py']
subprocess.run(['git','add','--',*changed],check=True)
for i in range(0,len(paths),40):subprocess.run(['git','add','-f','--',*paths[i:i+40]],check=True)
staged=subprocess.check_output(['git','diff','--cached','--name-only'],text=True).splitlines()
assert not any('/node_modules/' in p or '.sqlite3' in p or '/attended_profile/' in p or '/ui/' in p or '__pycache__' in p for p in staged)
subprocess.run(['git','diff','--cached','--check'],check=True)
print(len(staged),'files staged; public report bytes',sum((root/p).stat().st_size for p in paths))
