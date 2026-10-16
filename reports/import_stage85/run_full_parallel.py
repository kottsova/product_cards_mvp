"""Run every module selected by standard unittest discovery, without omissions."""
import sys,os,json,time,re,hashlib,subprocess,unittest
from pathlib import Path
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
root=Path(__file__).resolve().parents[2];out=Path(__file__).parent
sys.path.insert(0,str(root))
os.chdir(root)
paths=sorted(p for p in (root/'product_tool').rglob('*') if p.is_file() and p.suffix in {'.py','.html','.css','.js'})
fingerprint=lambda:{str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
before=fingerprint();start=time.monotonic()
loader=unittest.TestLoader();suite=loader.discover('tests',top_level_dir=str(root))
def cases(suite):
 for item in suite:
  if isinstance(item,unittest.TestSuite):yield from cases(item)
  else:yield item
standard=Counter(t.id() for t in cases(suite))
counts={};planned=Counter()
for path in sorted((root/'tests').rglob('test*.py')):
 module='.'.join(path.relative_to(root).with_suffix('').parts)
 selected=list(cases(loader.loadTestsFromName(module)))
 if selected:counts[module]=len(selected);planned.update(t.id() for t in selected)
assert not loader.errors,loader.errors
assert planned==standard,(standard-planned,planned-standard)
groups=[[] for _ in range(4)];loads=[0]*4
for module,count in sorted(counts.items(),key=lambda x:(-x[1],x[0])):
 slot=min(range(4),key=lambda i:loads[i]);groups[slot].append(module);loads[slot]+=count
assert len([m for g in groups for m in g])==len(set(counts))
plan=dict(discovery='unittest.TestLoader.discover tests, top_level_dir=repo',expected_tests=sum(counts.values()),expected_modules=len(counts),groups=[dict(modules=g,expected_tests=n) for g,n in zip(groups,loads)])
(out/'regression_plan.json').write_text(json.dumps(plan,indent=2),encoding='utf8')
env=dict(os.environ,PLAYWRIGHT_BROWSERS_PATH=str(root/'data/playwright_browsers'))
def run(index):
 phase=f'full_group_{index+1}';clock=time.monotonic()
 with (out/(phase+'.log')).open('w',encoding='utf8') as log:
  result=subprocess.run([str(root/'.venv/Scripts/python.exe'),'-X','utf8','-m','unittest',*groups[index],'-q'],cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT)
 body=(out/(phase+'.log')).read_text(encoding='utf8');numbers=re.findall(r'Ran (\d+) tests?',body)
 summary=dict(group=index+1,exit_code=result.returncode,seconds=round(time.monotonic()-clock,3),tests=int(numbers[-1]) if numbers else None,expected_tests=loads[index],summary=re.findall(r'(?m)^Ran .*|^OK.*|^FAILED.*|^FAIL:.*|^ERROR:.*',body))
 (out/(phase+'.json')).write_text(json.dumps(summary,indent=2),encoding='utf8');print(json.dumps(summary),flush=True)
 return summary
with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(run,range(4)))
valid=all(r['exit_code']==0 and r['tests']==r['expected_tests'] for r in results)
summary=dict(exit_code=0 if valid else 1,seconds=round(time.monotonic()-start,3),production_tree_unchanged=before==fingerprint(),execution='all standard-discovery modules in four independent processes',tests=sum(r['tests'] or 0 for r in results),expected_tests=plan['expected_tests'],modules=len(counts),no_modules_omitted_or_duplicated=True,groups=results,summary=[f"Ran {sum(r['tests'] or 0 for r in results)} tests",'OK' if valid else 'FAILED'])
if not summary['production_tree_unchanged']:summary['exit_code']=1
(out/'final_regression.json').write_text(json.dumps(summary,indent=2),encoding='utf8')
(out/'final_regression.log').write_text('\n'.join((out/f'full_group_{i+1}.log').read_text(encoding='utf8') for i in range(4)),encoding='utf8')
print(json.dumps(summary),flush=True);raise SystemExit(summary['exit_code'])
