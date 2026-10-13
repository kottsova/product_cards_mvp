"""Add only newly parsed exact-CFI fields from the separately recorded actual run."""
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from product_tool import jobs,card_evidence,normalization
from product_tool.adapters.common import SourceDocument,RawAttribute
R=Path(__file__).parent;db=R/'offline/batch.sqlite3';pid=49
actual=json.loads((R/'ps_hardware_live/49/result.json').read_text(encoding='utf8'))
ev=card_evidence.load(db,pid,'playstation')
assert actual['evidence']['hardware_model']==ev['hardware_model']=='CFI-1216A'
source=next(s for s in actual['sources'] if s['source_key']=='playstation_hardware')
assert source['match_level']=='hardware_confirmed' and not source['error']
old=[f for f in jobs.get_facts(db,pid) if f['source_key']=='playstation_hardware']
keys={f['normalized_name'] for f in old}
fresh=[f for f in actual['facts'] if f['source_key']=='playstation_hardware' and f['normalized_name'] not in keys]
doc=SourceDocument(source['source_key'],source['site_name'],source['url'],found_model=source['found_model'],match_level=source['match_level'],evidence=source['evidence'])
doc.attributes=[RawAttribute(f['raw_name'],f['raw_value'],f['section'],value_cell=f.get('value_cell')) for f in old+fresh]
jobs.save_source_document(db,pid,doc,update_attributes=True,update_photos=False,update_description=False)
jobs.resolve_product(db,pid)
new_rows=[r for r in actual['evidence']['raw_specs'] if r.get('hardware_code')=='CFI-1216A']
ev['raw_specs']=[r for r in ev['raw_specs'] if r.get('hardware_code')!='CFI-1216A']+new_rows
card_evidence.save(db,pid,'playstation',ev)
(R/'hardware_verification_merge.json').write_text(json.dumps({'original_live_observation':actual['observed_at'],'identity':'Exact CFI unchanged; only absent canonical keys added; original photo/document evidence retained','new_fields':[f['normalized_name'] for f in fresh]},indent=2)+'\n',encoding='utf8')
print('New actual exact-hardware fields:',len(fresh))
