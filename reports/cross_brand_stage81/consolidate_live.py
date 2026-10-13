"""Persist latest actual live observations, preserving their original phase artifacts."""
import sqlite3,json,shutil,hashlib
from pathlib import Path
from contextlib import closing
R=Path(__file__).parent;base=R/'final_live';delta=R/'final_delta_live';out=R/'qualified_live'
assert len(list(base.glob('*/result.json')))==103
assert len(list(delta.glob('*/result.json')))==17
out.mkdir(exist_ok=True);db=out/'batch.sqlite3'
with closing(sqlite3.connect(base/'batch.sqlite3')) as source,closing(sqlite3.connect(db)) as target:source.backup(target)
for phase in (base,delta):
 for log in phase.glob('*_log.json'):shutil.copy2(log,out/log.name) # Retain existing host stops/cooldown; never create a reset policy state.
manifest=[]
for inp in json.loads((R/'dataset.json').read_text(encoding='utf8'))['rows']:
 pid=inp['id'];phase=delta if (delta/str(pid)/'result.json').exists() else base
 dest=out/str(pid);dest.mkdir(exist_ok=True)
 result=json.loads((phase/str(pid)/'result.json').read_text(encoding='utf8'))
 result['original_observation_phase']=phase.name
 result['consolidation']='Persistence of actual live worker observations, not a fresh run and not replay'
 (dest/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 raw=phase/str(pid)/'raw_sources'
 if raw.exists():shutil.copytree(raw,dest/'raw_sources',dirs_exist_ok=True)
 manifest.append({'id':pid,'phase':phase.name,'observed_at':result['observed_at'],'original_job_id':result['job']['id'],'original_result_sha256':hashlib.sha256((phase/str(pid)/'result.json').read_bytes()).hexdigest()})
with closing(sqlite3.connect(delta/'batch.sqlite3')) as source,closing(sqlite3.connect(db)) as target:
 source.row_factory=sqlite3.Row;target.row_factory=sqlite3.Row
 tables={}
 for row in source.execute("SELECT name FROM sqlite_master WHERE type='table'"):
  name=row['name'];info=list(source.execute('PRAGMA table_info('+name+')'))
  if any(c['name']=='product_id' for c in info):tables[name]={'columns':info,'foreign':list(source.execute('PRAGMA foreign_key_list('+name+')'))}
 ordered=[];remaining=set(tables)
 while remaining:
  ready=sorted(name for name in remaining if all(f['table'] not in remaining for f in tables[name]['foreign']))
  assert ready,('Cyclic audit schema',remaining)
  ordered.extend(ready);remaining.difference_update(ready)
 remap={name:{} for name in tables};target.execute('PRAGMA foreign_keys=ON')
 with target:
  for pid in [m['id'] for m in manifest if m['phase']==delta.name]:
   for name in reversed(ordered):target.execute('DELETE FROM '+name+' WHERE product_id=?',(pid,))
   product=source.execute('SELECT * FROM products WHERE id=?',(pid,)).fetchone()
   for field in ('identity_json','original_values_json','updated_at'):
    if field in product.keys():target.execute('UPDATE products SET '+field+'=? WHERE id=?',(product[field],pid))
   for name in ordered:
    for row in source.execute('SELECT * FROM '+name+' WHERE product_id=?',(pid,)):
     values=dict(row);old_id=values.get('id')
     auto=next((c for c in tables[name]['columns'] if c['name']=='id' and c['pk'] and c['type'].upper()=='INTEGER'),None)
     if auto:values.pop('id')
     for fk in tables[name]['foreign']:
      field=fk['from'];old=values.get(field)
      if old is not None and fk['table'] in remap and fk['to']=='id':
       assert old in remap[fk['table']],(name,field,old)
       values[field]=remap[fk['table']][old]
     columns=list(values);sql='INSERT INTO '+name+' ('+','.join(columns)+') VALUES ('+','.join('?' for _ in columns)+')'
     cursor=target.execute(sql,[values[c] for c in columns])
     if old_id is not None:remap[name][old_id]=cursor.lastrowid if auto else old_id
  assert not list(target.execute('PRAGMA foreign_key_check'))
(out/'observation_manifest.json').write_text(json.dumps({'method':'Latest actual live observations; original source/trace artifacts remain unchanged','dataset_sha256':(R/'dataset.sha256').read_text().strip(),'rows':manifest},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print('Consolidated 103 actual live observations; 17 fresh affected reruns; FK check OK',flush=True)
