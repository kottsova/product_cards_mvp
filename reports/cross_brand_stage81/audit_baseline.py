"""Explicit raw -> stored fact -> projection lineage; counts are not assumed coverage."""
import sys,json,re
from pathlib import Path
from collections import Counter,defaultdict
sys.path.insert(0,str(Path(__file__).resolve().parents[2]));sys.stdout.reconfigure(encoding='utf8')
from product_tool import jobs,card_presentation,attribute_projection
R=Path(__file__).parent;phase=sys.argv[1] if len(sys.argv)>1 else 'baseline_live';root=R/phase;db=root/'batch.sqlite3'
def classify(reason):
 s=reason.casefold()
 for pattern,name in [(r'duplicat|alias|equivalent','duplicate'),(r'not yet canonically mapped|unsupported.*map','unsupported canonical mapping'),(r'malformed|invalid|empty','malformed'),(r'metadata|internal|logistic','logistics/internal'),(r'marketing|promotional','marketing'),(r'unproven|not_proven|not proven|unresolved|not confirmed|identity','unknown identity'),(r'variant|conditional|region|configurat|option|connectivity|case size|material','variant-sensitive')]:
  if re.search(pattern,s):return name
 return 'other'
def lists(x,path='evidence'):
 if isinstance(x,dict):
  for k,v in x.items():
   if isinstance(v,list) and k in {'raw_specs','raw_facts','original_raw_specs','accepted_specs','accepted_facts','admitted','rejected_specs','rejected_facts','candidates','configuration_candidates'}:
    yield path+'.'+k,v
   elif isinstance(v,dict):yield from lists(v,path+'.'+k)
def row_label(x):return x.get('raw_label',x.get('label',x.get('name','')))
def value(x):return x.get('value',x.get('raw_value',''))
report=[];inventory=defaultdict(dict);details={}
for file in sorted(root.glob('*/result.json'),key=lambda p:int(p.parent.name)):
 x=json.loads(file.read_text(encoding='utf8'));pid=x['input']['id'];canonical=x['canonical_output']
 lineage=defaultdict(list)
 for z in canonical:
  for name in {z['normalized_name'],z.get('derived_from'),z.get('refined_from')} - {None}:lineage[name].append(z['normalized_name'])
 missing=[];fact_trace=[]
 for f in x['facts']:
  target=lineage.get(f['normalized_name'],[]);reason=''
  if not target:
   if re.search(r'\((?:in|lbs?|oz|ft)\)$',f['raw_name'],re.I):reason='duplicate: imperial presentation omitted; counterpart must be checked'
   else:reason='parser loss / projection filter: accepted source fact omitted'
   missing.append({'fact_id':f['id'],'source':f.get('source_url') or next((s['url'] for s in x['sources'] if s['source_key']==f['source_key']),''),'section':f['section'],'label':f['raw_name'],'value':f['raw_value'],'canonical_name':f['normalized_name'],'reason':reason})
  fact_trace.append({'fact_id':f['id'],'canonical_name':f['normalized_name'],'output_names':target,'reason':reason or 'present / explicitly derived'})
 raw=[];rejections=[]
 for location,items in lists(x['evidence']):
  if location.endswith(('.raw_specs','.raw_facts')):
   raw.extend({'source':x['evidence'].get('pdp_url') or next((s['url'] for s in x['sources'] if s['url'] and not s['error']),''),'location':location,'section':z.get('section',z.get('source_section','')),'subsection':z.get('subsection',z.get('component','')),'label':row_label(z),'value':value(z),'native':z} for z in items if isinstance(z,dict))
  if location.endswith(('.rejected_specs','.rejected_facts','.candidates','.configuration_candidates')):
   rejections.extend({'location':location,'section':z.get('section',''),'label':row_label(z),'value':value(z),'reason':z.get('reason','candidate'),'classification':classify(z.get('reason','candidate'))} for z in items if isinstance(z,dict) and ('reason' in z or 'raw_label' in z))
 if not raw:
  for source in (file.parent/'raw_sources').glob('*.json'):
   s=json.loads(source.read_text(encoding='utf8'));raw.extend({'source':s['url'],**z} for z in s['raw_specs'])
 keys=Counter(z['normalized_name'] for z in canonical);dupes={k:n for k,n in keys.items() if n>1}
 labels=Counter(z['display_name'] for z in canonical);groups=card_presentation.present_card_rows(canonical,x['facts'],x['sources'],x['input']['category'])
 for role,sections in groups['groups'].items():
  for group,items in sections.items():
   for z in items:
    key=(group,z['display_name'],z['normalized_name'])
    e=inventory[x['input']['category']].setdefault(key,{'group':group,'label':z['display_name'],'key':z['normalized_name'],'role':role,'brands':set(),'models':set()});e['brands'].add(x['input']['brand']);e['models'].add(pid)
 data={'id':pid,'brand':x['input']['brand'],'category':x['input']['category'],'model':x['input']['model'],'raw_spec_rows':len(raw),'stored_facts':len(x['facts']),'canonical_rows':len(canonical),'rejected_rows':len(rejections),'rejected_reasons':dict(Counter(z['classification'] for z in rejections)),'unrepresented_stored_facts':len(missing),'unexplained_projection_loss':sum(not z['reason'].startswith('duplicate') for z in missing),'duplicate_output_keys':dupes,'generic_labels':sum(z['display_name']=='Дополнительная характеристика' for z in canonical),'english_labels':[z['display_name'] for z in canonical if not re.search('[А-Яа-яЁё]',z['display_name'])],'photos_saved':len(x['photos']),'photos_selected':sum(bool(z['selected']) for z in x['photos']),'photos_measured':sum(bool(z['verified_width']) for z in x['photos'])}
 report.append(data);details[str(pid)]={'raw_rows':raw,'rejections':rejections,'projection_missing':missing,'fact_output_lineage':fact_trace}
target=R/(phase+'_audit');target.mkdir(exist_ok=True)
(target/'loss_report.json').write_text(json.dumps({'observed_inputs':len(report),'rows':report,'details':details},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
inv={cat:[{**e,'brands':sorted(e['brands']),'models':sorted(e['models'])} for e in entries.values()] for cat,entries in sorted(inventory.items())}
(target/'category_inventory.json').write_text(json.dumps(inv,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print({'observed':len(report),'categories_observed':len(inv),'raw_rows':sum(x['raw_spec_rows'] for x in report),'stored':sum(x['stored_facts'] for x in report),'canonical':sum(x['canonical_rows'] for x in report),'projection_missing':sum(x['unexplained_projection_loss'] for x in report),'duplicate_keys':sum(len(x['duplicate_output_keys']) for x in report),'english_labels':len({s for x in report for s in x['english_labels']})})
