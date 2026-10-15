"""Repair only proven copies of the same import-mapping error; never rerun source jobs."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from openpyxl import load_workbook
from product_tool import storage
from product_tool.identity import ProductIdentity
root=Path(__file__).resolve().parents[2];out=Path(__file__).parent;db=root/'data/batches.sqlite3'
batch_id='70c329c089c2432fbe042651944c6acd';batch=storage.get_batch(db,batch_id)
assert (root/'data/backups/apple_first_card_before_repair.sqlite3').exists()
w=load_workbook(root/'data/uploads'/f'{batch_id}.xlsx',read_only=True,data_only=True)
rows=list(w.active.values);w.close()
assert rows[0][3].strip()=='Наименование на сайте' and rows[0][4]=='Цвет'
repairs=[]
for p in batch['products']:
    if p['id']==84:continue
    row=rows[p['row_number']-1]
    assert p['brand']==row[1]=='Apple' and p['search_code']==row[2]
    assert p['name']==row[2] and p['alternate_code']==row[1]
    assert str(row[3]).startswith('iPhone ')
    new={**p,'name':row[3],'alternate_code':'','variant_attributes':{'color':row[4]} if row[4] else {}}
    identity=ProductIdentity.from_product(new).to_dict()
    identity['input_provenance']={'name_column':4,'color_column':5,'hardware_column':3,'source':'original uploaded row; input configuration only'}
    repairs.append(dict(id=p['id'],row_number=p['row_number'],old_name=p['name'],new_name=row[3],old_alternate=p['alternate_code'],identity=identity))
with storage._connection(db) as c:
    for item in repairs:
        assert not c.execute("SELECT 1 FROM search_jobs WHERE product_id=? AND status IN ('queued','running')",(item['id'],)).fetchone()
        c.execute('UPDATE products SET name=?,alternate_code=?,identity_json=? WHERE id=?',(item['new_name'],'',json.dumps(item['identity'],ensure_ascii=False),item['id']))
    mapping={**batch['mapping'],'name':4,'fallback_code':None}
    c.execute('UPDATE batches SET mapping_json=? WHERE id=?',(json.dumps(mapping),batch_id))
(out/'remaining_input_repairs.json').write_text(json.dumps(dict(batch_id=batch_id,old_mapping=batch['mapping'],new_mapping=mapping,repairs=repairs,source_jobs_started=0),ensure_ascii=False,indent=2),encoding='utf8')
print('Original input metadata recovered:',len(repairs),'remaining rows; first-card evidence unchanged; no jobs started')
