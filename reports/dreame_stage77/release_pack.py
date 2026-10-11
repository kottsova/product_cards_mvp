"""Stage only public audit artifacts and authorized Stage 77 implementation."""
from pathlib import Path
import hashlib,json,subprocess
R=Path(__file__).parent
allowed={'.py','.json','.html','.img','.png','.md','.mjs','.pdf','.log'}
files=[p for p in R.rglob('*') if p.is_file() and (p.suffix in allowed or p.name=='Dreame_Stage77.xlsx') and p.name!='evidence_manifest.json']
assert all(not any(x in p.parts for x in ('attended_profile','chrome_profile')) for p in files)
assert all(p.suffix not in {'.sqlite3','.db'} for p in files)
assert all(p.stat().st_size<50_000_000 for p in files)
manifest={'public_artifacts_only':True,'excluded':'SQLite runtime stores, input workbooks, browser profiles, cookie/state values, temporary files','files':{p.relative_to(R).as_posix():{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(files)}}
(R/'evidence_manifest.json').write_bytes((json.dumps(manifest,indent=2)+'\n').encode('utf8'))
code=['.gitattributes','product_tool/adapters/dreame.py','product_tool/dreame_page.py','product_tool/normalization.py','product_tool/templates/product.html','product_tool/xiaomi_pipeline.py','tests/_pipeline_migration.py','tests/test_dreame_stage77.py']
paths=code+[p.relative_to(Path.cwd()).as_posix() for p in files]+[(R/'evidence_manifest.json').relative_to(Path.cwd()).as_posix()]
temp=Path('data/dreame_stage77_paths.txt');temp.write_bytes(b'\0'.join(str(p).encode('utf8') for p in paths)+b'\0')
subprocess.run(['git','add','-f','--pathspec-from-file='+str(temp),'--pathspec-file-nul'],check=True)
staged=subprocess.check_output(['git','diff','--cached','--name-only','-z']).decode('utf8').split('\0');staged=[p for p in staged if p]
assert set(staged)==set(paths),(set(staged)-set(paths),set(paths)-set(staged))
print({'staged_files':len(staged),'artifact_bytes':sum(p.stat().st_size for p in files),'excluded_private_runtime':True})
