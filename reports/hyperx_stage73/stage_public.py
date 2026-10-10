"""Stage the authorized code and public evidence only, after Stage73 PASS."""
import json,subprocess,hashlib
from pathlib import Path
R=Path(__file__).parent
assert json.loads((R/'acceptance_summary.json').read_text(encoding='utf8'))['verdict']=='HyperX adapter production-ready for controlled use'
reg=json.loads((R/'regression_release.json').read_text(encoding='utf8'))
assert reg['exit_code']==0 and reg['source_tree_unchanged']
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==sha for p,sha in reg['source_manifest'].items())
code=[p for p in subprocess.check_output(['git','diff','--name-only'],text=True).splitlines() if p.startswith('product_tool/')]
subprocess.run(['git','diff','--check'],check=True)
subprocess.run(['git','add','--','.gitattributes',*code,'tests/_pipeline_migration.py','tests/test_hyperx_stage73.py',R.as_posix()],check=True)
public=[p.as_posix() for p in R.rglob('*') if p.is_file() and (p.suffix in {'.log','.pdf','.xlsx'} or p.name.endswith('_log.json'))]
if public:subprocess.run(['git','add','-f','--',*public],check=True)
staged=subprocess.check_output(['git','diff','--cached','--name-only'],text=True).splitlines()
assert not any(p.startswith('data/') or '.sqlite' in p or 'Cookies' in p or '__pycache__' in p for p in staged)
subprocess.run(['git','diff','--cached','--check'],check=True)
print(len(staged),'authorized code/public evidence paths staged; no profile/cookies/SQLite')
