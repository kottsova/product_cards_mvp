import sys,subprocess,time,json,hashlib,re,os
from pathlib import Path
root=Path(__file__).resolve().parents[2];out=Path(__file__).parent;phase=sys.argv[1]
paths=sorted(p for p in (root/'product_tool').rglob('*') if p.is_file() and p.suffix in {'.py','.html','.css','.js'})
fingerprint=lambda:{str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
before=fingerprint();start=time.monotonic();env=dict(os.environ)
if (root/'data/playwright_browsers').exists():env['PLAYWRIGHT_BROWSERS_PATH']=str(root/'data/playwright_browsers')
arguments=sys.argv[2:] or ['discover','-s','tests','-q']
with (out/(phase+'.log')).open('w',encoding='utf8') as log:
 r=subprocess.run([str(root/'.venv/Scripts/python.exe'),'-X','utf8','-m','unittest',*arguments],cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT)
tail=(out/(phase+'.log')).read_text(encoding='utf8');summary=dict(exit_code=r.returncode,seconds=round(time.monotonic()-start,3),production_tree_unchanged=before==fingerprint(),summary=re.findall(r'(?m)^Ran .*|^OK.*|^FAILED.*|^FAIL:.*|^ERROR:.*',tail))
(out/(phase+'.json')).write_text(json.dumps(summary,indent=2),encoding='utf8');print(json.dumps(summary),flush=True);print(tail[-4500:],flush=True)
raise SystemExit(r.returncode)
