"""Bounded explicit staging; never traverse browser profiles or node_modules junction."""
from pathlib import Path
import os,json,subprocess,hashlib
R=Path(__file__).parent;root=Path.cwd();report=[]
assert json.loads((R/'acceptance_summary.json').read_text(encoding='utf8'))['audit']=='PASS'
assert json.loads((R/'regression_release.json').read_text(encoding='utf8'))['exit_code']==0
skip={'node_modules','ui','__pycache__','attended_profile','attended_search'}
for directory,dirs,files in os.walk(R,followlinks=False):
 dirs[:]=[n for n in dirs if n not in skip and not os.path.islink(Path(directory)/n) and not os.path.isjunction(Path(directory)/n)]
 for name in files:
  p=Path(directory)/name
  if '.sqlite3' in name or name.endswith('.pyc'):continue
  if name.endswith('.log') and (p.parent!=R or name not in {'regression_release.log','artifact_render.log'}):continue
  assert p.stat().st_size<90_000_000
  report.append(str(p.relative_to(root)))
changed=subprocess.check_output(['git','diff','--name-only'],text=True).splitlines();changed.append('tests/test_xbox_stage69.py')
assert not any(n.startswith('reports/xbox_stage68/') for n in changed)
subprocess.run(['git','add','--',*changed],check=True)
for i in range(0,len(report),40):subprocess.run(['git','add','-f','--',*report[i:i+40]],check=True)
staged=subprocess.check_output(['git','diff','--cached','--name-only'],text=True).splitlines()
assert not any('/node_modules/' in n or '/attended_profile/' in n or '/attended_search/' in n or '.sqlite3' in n for n in staged)
assert hashlib.sha256(Path('reports/xbox_stage68/dataset.json').read_bytes()).hexdigest()=='556dfe669181b1959e1d21dd52ed491f78719744bdbdab3442bef981de76191c'
print('Explicit staged files',len(staged),'public report bytes',sum((root/n).stat().st_size for n in report))
