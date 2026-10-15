import subprocess,time,json,hashlib
from pathlib import Path
root=Path(__file__).resolve().parents[2];out=Path(__file__).parent
paths=sorted((root/'product_tool').rglob('*.py'))
before={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
start=time.monotonic()
with (out/'regression.log').open('w',encoding='utf8') as log:
    result=subprocess.run([str(root/'.venv/Scripts/python.exe'),'-X','utf8','-m','unittest','discover','-s','tests','-q'],cwd=root,stdout=log,stderr=subprocess.STDOUT)
after={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
report={'exit_code':result.returncode,'seconds':round(time.monotonic()-start,3),'production_tree_unchanged':before==after,'log':'regression.log'}
(out/'regression.json').write_text(json.dumps(report,indent=2),encoding='utf8')
print(json.dumps(report),flush=True)
print((out/'regression.log').read_text(encoding='utf8')[-6000:],flush=True)
raise SystemExit(result.returncode)
