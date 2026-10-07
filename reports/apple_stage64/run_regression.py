from pathlib import Path
import subprocess,sys,time,json,re,os
root=Path('reports/apple_stage64');env=os.environ.copy();env['PYTHONIOENCODING']='utf-8';env['PLAYWRIGHT_BROWSERS_PATH']=str(Path('.venv/playwright-browsers').resolve())
source_paths=sorted(list(Path('product_tool').rglob('*.py'))+list(Path('product_tool/templates').rglob('*.html'))+list(Path('tests').glob('*.py'))+[Path('product_tool/requirements.txt')])
fingerprint=lambda:{str(p):__import__('hashlib').sha256(p.read_bytes()).hexdigest() for p in source_paths}
before=fingerprint()
start=time.monotonic()
with (root/'regression_release.log').open('w',encoding='utf-8') as log:
 result=subprocess.run([sys.executable,'-m','tests'],stdout=log,stderr=subprocess.STDOUT,env=env)
text=(root/'regression_release.log').read_text(encoding='utf-8')
summary={'exit_code':result.returncode,'source_tree_unchanged':before==fingerprint(),'elapsed_seconds':round(time.monotonic()-start,3),'result':re.findall(r'^Ran .*|^FAILED.*|^OK$',text,re.M),'command':f'{sys.executable} -m tests','network':'offline test guard','browser_path':env['PLAYWRIGHT_BROWSERS_PATH']}
(root/'regression_release.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary),flush=True)
raise SystemExit(result.returncode if before==fingerprint() else 2)
