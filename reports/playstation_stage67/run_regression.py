"""Full offline regression; all application/test sources immutable during execution."""
from pathlib import Path
import subprocess,hashlib,json,time,os,sys
r=Path('reports/playstation_stage67')
def digest():return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for root in ('product_tool','tests') for p in Path(root).rglob('*') if p.is_file() and p.suffix in {'.py','.js','.html'}}
before=digest();start=time.monotonic();env=os.environ.copy();env['PLAYWRIGHT_BROWSERS_PATH']=str(Path('.venv/playwright-browsers').resolve());env['PYTHONIOENCODING']='utf-8'
with (r/'regression_release.log').open('w',encoding='utf-8') as log:code=subprocess.call([sys.executable,'-m','tests'],stdout=log,stderr=subprocess.STDOUT,env=env)
lines=(r/'regression_release.log').read_text(encoding='utf-8').splitlines();result=dict(exit_code=code,source_tree_unchanged=before==digest(),elapsed_seconds=time.monotonic()-start,result=[s for s in lines if s.startswith('Ran ') or s=='OK' or s.startswith('FAILED')],command=f'{sys.executable} -m tests',network='offline test guard',source_manifest=before)
(r/'regression_release.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print({k:v for k,v in result.items() if k!='source_manifest'},flush=True);assert code==0 and result['source_tree_unchanged']
