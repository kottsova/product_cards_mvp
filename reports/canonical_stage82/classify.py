"""One explainable decision per frozen unsupported row; no live claim."""
import sys,json,re,hashlib
from pathlib import Path
from collections import Counter,defaultdict
sys.path.insert(0,str(Path(__file__).resolve().parents[2]));sys.stdout.reconfigure(encoding='utf8')
from product_tool import jobs,card_evidence,photo_inventory,attribute_projection
from product_tool.attribute_lineage import linked_facts,text_key,source_row_matches,technical_role
R=Path(__file__).parent;S=R.parent/'cross_brand_stage81';db=R/'offline/batch.sqlite3'
frozen=json.loads((R/'unsupported_inventory_frozen.json').read_text(encoding='utf8'))['rows']
def buckets(ev,keys):
 for k in keys:
  for r in ev.get(k,[]):
   if isinstance(r,dict):yield r
decisions=[];cache={}
for row in frozen:
 pid=row['product_id']
 if pid not in cache:
  product=jobs.get_product(db,pid);ev=card_evidence.load(db,pid,photo_inventory.evidence_kind(product)) or {}
  banks=[x for p in (R/'offline').glob(f'{pid}_*_parser.json') for x in [json.loads(p.read_text(encoding='utf8'))] if x.get('parser_source_key')]
  cache[pid]=(ev,jobs.get_facts(db,pid),jobs.get_source_pages(db,pid),attribute_projection.final_attribute_rows(db,pid),banks)
 ev,facts,sources,output,banks=cache[pid];raw=row['original_raw_record'];source=next((s for s in sources if s['url']==row['source']),{})
 bank=ev.get('model_evidence',{}) if source.get('source_key')=='apple_model' else ev
 admissions=list(buckets(bank,('accepted_specs','accepted_facts','admitted')))+[a for a in bank.get('raw_specs',[]) if a.get('derived_fields')]
 current=[f for f in facts if f['source_key']==source.get('source_key')]
 related=linked_facts(raw,admissions,current);basis='Parser-authored exact source raw→target relation'
 resolved_source=row['source']
 if not related:
  for candidate_bank in banks:
   candidate_admissions=list(buckets(candidate_bank,('accepted_specs','accepted_facts','admitted')))
   candidate_facts=[f for f in facts if f['source_key']==candidate_bank['parser_source_key']]
   links=linked_facts(raw,candidate_admissions,candidate_facts)
   if links:
    related=links;bank=candidate_bank;admissions=candidate_admissions;current=candidate_facts;resolved_source=candidate_bank['parser_source_url']
    basis='Reparsed qualified source carries exact raw→target relation; original Stage81 default/empty provenance corrected'
    break
 if not related and row['brand']=='Apple' and source.get('source_key')=='apple':
  # Only explicit model-stable parser records from the already qualified same
  # model join; no memory/color/layout/revision values may cross sources.
  stable=[a for a in ev.get('model_evidence',{}).get('admitted',[]) if a.get('scope')=='model-stable']
  related=linked_facts(raw,stable,[f for f in facts if f['source_key']=='apple_model'])
  basis='Same qualified exact model, explicit model-stable parser origin; target source remains Apple Tech Specs'
 if not related and row['brand']=='PlayStation' and raw.get('hardware_code'):
  from product_tool.playstation_specs import LABELS
  name=LABELS.get(row['raw_label'])
  page=next((s for s in sources if s['source_key']=='playstation_hardware' and not s['error']),None)
  if name and page and ev.get('hardware_model')==raw['hardware_code']:
   targets=[{'section':row['section'],'raw_label':row['raw_label'],'raw_value':row['raw_value'],'derived_fields':[{'name':name,'value':row['raw_value']}]}]
   related=linked_facts(raw,targets,[f for f in facts if f['source_key']=='playstation_hardware'])
   if related:resolved_source=page['url'];basis='Existing exact-hardware parser label dictionary and verbatim value; PDF hardware relation unchanged'
 if not related and row['brand']=='PlayStation' and row['raw_label']=='Unmapped specification line' and raw.get('hardware_code')==ev.get('hardware_model'):
  hardware=[f for f in facts if f['source_key']=='playstation_hardware']
  prefix,sep,body=str(row['raw_value']).partition(':')
  labels={'Type':'Тип лазера оптического привода','BD Wavelength':'Длина волны лазера BD','DVD Wavelength':'Длина волны лазера DVD'}
  if sep and prefix in labels:
   related=[f for f in hardware if f['raw_name']==labels[prefix] and text_key(f['raw_value'])==text_key(body)]
  elif str(row['raw_value']).startswith(('BD-ROM','BD-R/RE','DVD ~')):
   related=[f for f in hardware if f['raw_name']=='Форматы чтения оптического привода' and text_key(row['raw_value']) in text_key(f['raw_value'])]
  if related:basis='Hardware table parser recovered explicit optical labels/continuation; target verified by actual exact-CFI rerun'
 if not related and row['brand']=='Electrolux':
  from product_tool.electrolux_page import mapped
  attrs=mapped({'label':row['raw_label'],'value':row['raw_value'],'section':row['section']})
  ledger=[{**raw,'derived_fields':[{'name':a.name,'value':a.value,'section':a.section} for a in attrs]}]
  related=linked_facts(raw,ledger,current)
  if related:basis='Existing scoped Electrolux native-field mapper; exact published axis order; original PNC/conflict status unchanged'
 if not related and row['brand']=='PlayStation' and raw.get('scope')=='model' and row['section']=='Own product features':
  page=next((s for s in sources if s['source_key']=='playstation_model' and not s['error']),None)
  if page:
   related=[f for f in facts if f['source_key']=='playstation_model' and text_key(f['raw_name'])==text_key(row['raw_label'])]
   if related:resolved_source=page['url'];basis='Original parser-authored model-scoped feature name linked to its stored accepted target; surrounding prose is retained, not compared to a boolean/scalar value'
 keys={key for r in output for key in [r['normalized_name'],r.get('derived_from'),r.get('refined_from'),*r.get('derived_from_names',[])] if key}
 related=[f for f in related if f['normalized_name'] in keys]
 reasons=[r.get('reason','') for b in [bank,*banks] for r in buckets(b,('rejected_specs','rejected_facts','candidates','configuration_candidates')) if source_row_matches(raw,r)]
 reason='; '.join(dict.fromkeys(reasons));value=text_key(row['raw_value']);label=text_key(row['raw_label']);sec=text_key(row['section']);alltext=label+' '+value
 kind=action=why=None
 artifact=row['brand']=='Razer' and re.search(r'Impedance:|Signal-to-noise ratio:',row['raw_value']) and sec in {'headphones','microphone'}
 if artifact:
  origins=[a for a in admissions if text_key(a.get('section'))==sec and text_key(a.get('value')) in value]
  related=[]
  for a in origins:related.extend(linked_facts(a,[a],current))
  related=[f for f in related if f['normalized_name'] in keys]
  if related:kind='G';action='parser_fixed';why='SSR component cell now split at explicit colon labels, with headphone/microphone scopes retained'
  else:kind='C';action='candidate';why='SSR compound row is split by the repaired parser, but the legacy component/model/configuration relation does not produce an admitted current canonical target'
 elif related and basis.startswith('Hardware table parser recovered'):
  kind='G';action='parser_fixed';why=basis
 elif related:
  role='feature' if any(technical_role(f['raw_name'],f['section'])=='feature' for f in related) else 'core'
  kind='B' if role=='feature' else 'A';action='feature' if role=='feature' else 'mapped';why=basis
 elif label in {'warranty','support period'} or re.search(r'in this manual\.?$|^notice\.$|^the operating instructions|^the product\.$|^\*\d+ (?:usability|use the included)|^ps5 console.s usb|^\* this time is estimated',value):
  kind='E';action='excluded_support';why='Warranty/support lifecycle, legal disclaimer or usage/charging instructions; not a product attribute'
 elif re.fullmatch(r'\d{2}\s*mm|wi-fi models|wi-fi \+ cellular models',value) or label=='unmapped specification line' and re.match(r'^playstation.*console$|^main processor$|^single-chip custom processor$|^laser$|^optical drive \(read-only\)$|^country of production\b',value):
  kind='F';action='excluded_internal';why='Published identity/subsection/table heading or origin metadata, not an independent technical value'
 elif label=='privacy' or re.search(r'centered around you|built from the ground up to protect',value):
  kind='D';action='excluded_marketing';why='General privacy/AI positioning without a standalone measurable or explicitly named device capability'
 elif label=='unmapped specification line' and re.match(r'^voltage |^power:|.*availability of ssd capacity may vary|^\*1 a portion|^maintenance and additional options',value):
  kind='C';action='candidate';why='Supply/battery/optical subcomponent or nominal-versus-usable storage scope is not bound by this legacy raw line'
 elif re.search(r'^(learn more|see .*report|tap to zoom|read |how to)|user guide|troubleshoot|design and specifications are subject|software version in use|manually|drivers available',value):
  kind='E';action='excluded_support';why='Help, document reference, interactive control or legal/support instruction; no independent product value'
 elif re.search(r'configuration|variant|region|material|case size|connectivity|column order|exact.*(?:hardware|revision)|transport-specific|bundle|kit|own.*(?:variant|sku)|component.*routing|layout',reason,re.I) or sec in {'acoustic performance','material and finish','sim card','apple pay'}:
  kind='C';action='candidate';why=reason or 'Explicit configuration/region/component test scope; exact requested relation is not qualified'
 elif re.search(r'marketing|promotional|company process',reason,re.I) or re.search(r'most (?:advanced|powerful)|strongest privacy|designed to|progress toward|business-as-usual|commitment|zero waste program|manufacturing electricity|assembly sites',value):
  kind='D';action='excluded_marketing';why=reason or 'Promotional/company-process statement without an independent device technical value'
 elif re.search(r'heading|metadata|identity_or_software_help|power/accessory metadata|model.*number|chip metadata',reason,re.I) or label in {'support period','warranty','unmapped specification line'} and re.fullmatch(r'[\W\d]+|storage|system|console|power|maximum rated power|mass|operating temperature|external dimensions',value):
  kind='F';action='excluded_internal';why=reason or 'Table heading, model identifier or document layout metadata; raw kept'
 else:
  kind='H';action='ambiguous'
  raw_seen=any(source_row_matches(raw,r) for b in banks for r in b.get('raw_specs',b.get('raw_facts',[])))
  if not raw_seen:why='Historical raw provenance gap: this label/value is not reproduced in the qualified saved source parser inventory; original owner path/variant cannot be recovered safely. Field meaning may be technical; no current-source confirmation is inferred.'
  elif label=='soc die size':why='Source prints mm without a squared area unit or axis; die area versus linear dimension is not established'
  else:why=reason or 'Raw row reproduced, but no unique admitted target under its source/component/identity scope; source-specific field meaning or value relation remains unqualified'
 target_names=sorted({f['normalized_name'] for f in related});shown=[r for r in output if r['normalized_name'] in target_names or r.get('derived_from') in target_names or r.get('refined_from') in target_names or set(r.get('derived_from_names',[]))&set(target_names)]
 resolved_component=next((scope for pattern,scope in [(r'microphone|микрофон','microphone'),(r'headphone|наушник','headphones'),(r'charging case|кейс','case'),(r'station|станци','station'),(r'robot|робот','robot'),(r'package|packaging|упаков','package'),(r'controller|dualsense|контроллер','controller')] if re.search(pattern,row['section']+' '+row['raw_label'],re.I)),raw.get('component') or 'device' if source.get('source_key') else 'unresolved')
 decisions.append({**row,'resolved_source':resolved_source,'source_correction':resolved_source!=row['source'],'resolved_component_scope':resolved_component,'reproduced_in_qualified_source_inventory':any(source_row_matches(raw,r) for b in banks for r in b.get('raw_specs',b.get('raw_facts',[]))),'owned_parser_rejections':list(dict.fromkeys(reasons)),'class':kind,'action':action,'decision_reason':why,'role':'feature' if kind=='B' else 'core' if kind=='A' else None,'canonical_targets':sorted({r['normalized_name'] for r in shown}),'output_labels':sorted({r['display_name'] for r in shown}),'parent_groups':sorted({r['parent_group'] for r in shown}),'target_sources':sorted({next((s['url'] for s in sources if s['source_key']==f['source_key']),'') for f in related})})
assert len(decisions)==1643 and len({r['row_id'] for r in decisions})==1643
assert all(r['decision_reason'] and r['class'] in 'ABCDEFGH' for r in decisions)
assert all(r['canonical_targets'] for r in decisions if r['class'] in {'A','B'}),'Mapped decision without native output target'
counts=Counter(r['class'] for r in decisions);actions=Counter(r['action'] for r in decisions)
def save(name,data):(R/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
save('classification.json',{'baseline':1643,'classes':dict(counts),'actions':dict(actions),'mode':'Offline classification; actual live reruns reported separately','rows':decisions})
for pid in {r['product_id'] for r in decisions}:
 card_evidence.save(db,pid,'canonical_mapping_audit',{'baseline_commit':'6a6a20e4950334028e696873544debd48e461477','scope':'Frozen raw fields and explicit classification, not additional confirmed product facts','rows':[r for r in decisions if r['product_id']==pid]})
save('remaining_ambiguous.json',[r for r in decisions if r['class']=='H'])
save('classification_groups.json',[{'brand':b,'label':l,'count':n,'classes':dict(Counter(r['class'] for r in decisions if r['brand']==b and r['raw_label']==l))} for (b,l),n in Counter((r['brand'],r['raw_label']) for r in decisions).most_common()])
print({'classes':dict(counts),'actions':dict(actions),'ambiguous_groups':Counter((r['brand'],r['raw_label']) for r in decisions if r['class']=='H').most_common(45)},flush=True)
