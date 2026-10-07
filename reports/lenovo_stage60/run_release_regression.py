from pathlib import Path
import subprocess,sys,time,json,re,os
root=Path('reports/lenovo_stage60');env=os.environ.copy();env['PYTHONIOENCODING']='utf-8';env['PLAYWRIGHT_BROWSERS_PATH']=str(Path('.venv/playwright-browsers').resolve())
start=time.monotonic()
with (root/'regression_release.log').open('w',encoding='utf-8') as log:
 result=subprocess.run([sys.executable,'-m','tests'],stdout=log,stderr=subprocess.STDOUT,env=env)
text=(root/'regression_release.log').read_text(encoding='utf-8')
summary={'exit_code':result.returncode,'elapsed_seconds':round(time.monotonic()-start,3),'result':re.findall(r'^Ran .*|^FAILED.*|^OK$',text,re.M),'command':f'{sys.executable} -m tests','network':'offline test guard','browser_path':env['PLAYWRIGHT_BROWSERS_PATH']}
(root/'regression_release.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary),flush=True)
raise SystemExit(result.returncode)
