"""Full offline regression with before/after source integrity manifest."""
from pathlib import Path
import subprocess,hashlib,json,time,os,sys
root=Path(__file__).parent;label=sys.argv[1] if len(sys.argv)>1 else 'qualification'
def digest():
 return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for directory in ('product_tool','tests') for p in Path(directory).rglob('*') if p.is_file() and p.suffix in {'.py','.js','.html','.css'}}
before=digest();start=time.monotonic();env=os.environ.copy()
env['PLAYWRIGHT_BROWSERS_PATH']=str(Path('.venv/playwright-browsers').resolve());env['PYTHONIOENCODING']='utf-8'
log=root/('regression_'+label+'.log')
with log.open('w',encoding='utf8') as output:code=subprocess.call([sys.executable,'-m','tests'],stdout=output,stderr=subprocess.STDOUT,env=env)
lines=log.read_text(encoding='utf8').splitlines()
result={'exit_code':code,'source_tree_unchanged':before==digest(),'elapsed_seconds':round(time.monotonic()-start,2),'result':[s for s in lines if s.startswith('Ran ') or s=='OK' or s.startswith('FAILED')],'command':str(sys.executable)+' -m tests','network':'offline test guard','source_manifest':before}
(root/('regression_'+label+'.json')).write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
print({k:v for k,v in result.items() if k!='source_manifest'},flush=True)
assert code==0 and result['source_tree_unchanged']
