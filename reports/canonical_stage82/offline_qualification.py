"""Current parsers over Stage 81 observations: offline, never counted as live."""
import sys,json,sqlite3,shutil
from contextlib import closing
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]));sys.stdout.reconfigure(encoding='utf8')
from product_tool import jobs,card_evidence,photo_inventory,attribute_projection
from product_tool.apple_identity import parse_model
from product_tool.adapters.apple import parse_page as apple_order_parse
from product_tool.razer_page import parse_page as razer_parse
from product_tool.xiaomi_page import parse_page as xiaomi_parse
from product_tool.xbox_page import parse_page as xbox_parse
from product_tool.xbox_identity import family as xbox_family
from product_tool.dreame_page import parse_page as dreame_parse
from product_tool.electrolux_page import parse as electrolux_parse
from product_tool.adapters.playstation import parse_page as ps_parse
from product_tool.playstation_identity import model_key as ps_key
R=Path(__file__).parent;S=R.parent/'cross_brand_stage81';out=R/'offline';out.mkdir(exist_ok=True);db=out/'batch.sqlite3'
if not sys.argv[1:]:
 with closing(sqlite3.connect(S/'qualified_live/batch.sqlite3')) as source,closing(sqlite3.connect(db)) as target:source.backup(target)
inputs=json.loads((S/'dataset.json').read_text(encoding='utf8'))['rows'];changes=[]
for inp in inputs:
 if sys.argv[1:] and str(inp['id']) not in sys.argv[1:]:continue
 pid=inp['id'];p=jobs.get_product(db,pid);kind=photo_inventory.evidence_kind(p);ev=card_evidence.load(db,pid,kind) or {};old=len(attribute_projection.final_attribute_rows(db,pid))
 for file in (S/'qualified_live'/str(pid)/'raw_sources').glob('*.json'):
  data=json.loads(file.read_text(encoding='utf8'));html=file.with_suffix('.html')
  if not html.exists() or data['error']:continue
  parsed=None
  if inp['brand']=='Apple' and data['source']=='apple_model':
   base=ev.get('model_evidence',{});key=base.get('model_key')
   if key:parsed=parse_model(html.read_text(encoding='utf8'),data['url'],key,ev.get('configuration_fields',{}))
  elif inp['brand']=='Apple' and data['source']=='apple':parsed=apple_order_parse(html.read_text(encoding='utf8'),data['url'],inp['article'])
  elif inp['brand']=='Razer':parsed=razer_parse(html.read_text(encoding='utf8'),data['url'],inp['article'],inp['name'],inp['category'],model_evidence=ev.get('identity'))
  elif inp['brand']=='Xiaomi':parsed=xiaomi_parse(html.read_text(encoding='utf8'),data['url'],inp['article'],inp['name'],inp['category'])
  elif inp['brand']=='Xbox':parsed=xbox_parse(html.read_text(encoding='utf8'),data['url'],inp['article'],xbox_family(inp['name']),inp['region'],name=inp['name'],catalog_bindings=[r for r in ev.get('identity_relations',[]) if r.get('value')])
  elif inp['brand']=='Dreame':parsed=dreame_parse(html.read_text(encoding='utf8'),data['url'],inp['article'],inp['name'],inp['category'])
  elif inp['brand']=='Electrolux':parsed=electrolux_parse(html.read_text(encoding='utf8'),data['url'],inp['model'],requested_pnc=inp.get('input_pnc') or '',requested_region=inp['region'],catalog_relations=[r for r in ev.get('pnc_inventory',[]) if isinstance(r,dict)])
  elif inp['brand']=='PlayStation':parsed=ps_parse(html.read_text(encoding='utf8'),data['url'],inp['article'],ps_key(inp['name']))
  if not parsed:continue
  doc,audit=parsed
  if doc.error or not doc.attributes:continue
  audit['parser_source_url']=data['url'];audit['parser_source_key']=doc.source_key
  (out/f'{pid}_{data["source"]}_parser.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
  if inp['brand'] not in {'Apple','Razer','Xiaomi'}:continue
  if inp['brand']=='Apple' and data['source']=='apple':
   # Order enrichment is a separate production step (catalog/title records).
   # Parser-only QA must retain its already-proven exact same-order overrides.
   original=[f for f in jobs.get_facts(S/'qualified_live/batch.sqlite3',pid) if f['source_key']=='apple' and f['section']=='Configuration']
   from product_tool.normalization import normalize_name
   protected={f['normalized_name'] for f in original}
   from product_tool.adapters.common import RawAttribute
   doc.attributes=[a for a in doc.attributes if normalize_name(a.name,a.section) not in protected]+[RawAttribute(f['raw_name'],f['raw_value'],f['section'],value_cell=f.get('value_cell')) for f in original]
   audit['preserved_qualified_order_overrides']=[{'name':f['raw_name'],'value':f['raw_value'],'source':data['url']} for f in original]
  jobs.save_source_document(db,pid,doc,update_attributes=True,update_photos=False,update_description=False)
  if inp['brand']=='Apple' and data['source']=='apple_model':ev['model_evidence']=audit
  else:
   # This parser-only qualification never overwrites documents/photo evidence.
   for k in ('raw_specs','accepted_specs','rejected_specs','configuration_candidates'): 
    if k in audit:ev[k]=audit[k]
 card_evidence.save(db,pid,kind,ev);jobs.resolve_product(db,pid)
 after=len(attribute_projection.final_attribute_rows(db,pid))
 if after!=old:changes.append({'id':pid,'brand':inp['brand'],'before':old,'after':after})
(R/'offline_parser_changes.json').write_text(json.dumps({'mode':'offline parser success, not live','changes':changes},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(changes,flush=True)
