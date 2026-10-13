"""Freeze the exact Stage 81 unsupported population, before mapping cleanup."""
import hashlib,json,re,sys
from pathlib import Path
from collections import defaultdict
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from product_tool import jobs,card_evidence,photo_inventory
R=Path(__file__).parent;S=R.parent/'cross_brand_stage81'
report=json.loads((S/'qualified_live_audit/loss_report.json').read_text(encoding='utf8'))
inputs={r['id']:r for r in json.loads((S/'dataset.json').read_text(encoding='utf8'))['rows']}
db=S/'qualified_live/batch.sqlite3'
rows=[];groups=defaultdict(list)
for product_row in report['rows']:
 pid=product_row['id'];inp=inputs[pid]
 product=jobs.get_product(db,pid);sources=jobs.get_source_pages(db,pid)
 ev=card_evidence.load(db,pid,photo_inventory.evidence_kind(product)) or {}
 for index,raw in enumerate(report['details'][str(pid)]['raw_rows']):
  if raw['classification']!='unsupported canonical mapping':continue
  source=next((s for s in sources if s['url']==raw['source']),{})
  row={'row_id':f'{pid}:{index}','product_id':pid,'brand':inp['brand'],'category':inp['category'],'model':inp['model'],
       'source':raw['source'],'section':raw.get('source_section',raw.get('section','')),
       'subsection':raw.get('subsection',raw.get('component','')),'raw_label':raw.get('raw_label',raw.get('label','')),
       'raw_value':raw.get('raw_value',raw.get('value','')),'region':source.get('region') or inp.get('region') or 'not published',
       'component_scope':raw.get('component_scope',raw.get('component','not yet classified')),
       'identity_relation':{'source_match_level':source.get('match_level'),'source_key':source.get('source_key'),
                            'reported_identity':ev.get('identity',{}),'input_configuration':inp.get('input_configuration',{}),'input_pnc':inp.get('input_pnc')},
       'previous_reason':raw['reason'],'original_raw_record':raw}
  rows.append(row)
  group=re.sub(r'[^\w]+',' ',row['raw_label'].casefold()).strip()
  groups[group].append(row)
assert len(rows)==1643
path=R/'unsupported_inventory_frozen.json'
assert not path.exists(),'Frozen inventory already exists'
path.write_text(json.dumps({'baseline_commit':'6a6a20e4950334028e696873544debd48e461477','count':1643,'rows':rows},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
(R/'unsupported_inventory_frozen.sha256').write_text(hashlib.sha256(path.read_bytes()).hexdigest()+'\n',encoding='utf8')
ranked=[{'normalized_label':label,'frequency':len(items),'brands':sorted({r['brand'] for r in items}),
         'categories':sorted({r['category'] for r in items}),'models':sorted({r['product_id'] for r in items}),
         'labels':sorted({r['raw_label'] for r in items}),'row_ids':[r['row_id'] for r in items],
         'examples':[{'section':r['section'],'value':r['raw_value']} for r in items[:3]]} for label,items in groups.items()]
ranked.sort(key=lambda g:(-len(g['brands']),-len(g['models']),-g['frequency'],g['normalized_label']))
(R/'label_groups.json').write_text(json.dumps(ranked,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print({'frozen':len(rows),'label_groups':len(groups),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
