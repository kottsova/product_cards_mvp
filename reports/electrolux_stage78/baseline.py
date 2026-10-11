"""Unmodified ordinary worker baseline; no Electrolux-specific adapter or URL seed."""
import sys,json,sqlite3,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from openpyxl import Workbook
from product_tool import jobs,worker,importer,readiness,discovery_trace
R=Path(__file__).parent
if len(sys.argv)>1:R=R/sys.argv[1];R.mkdir(parents=True,exist_ok=True)
model=sys.argv[2] if len(sys.argv)>2 else 'EFI61141B';category='Духовые шкафы' if model=='EOF6P46X' else 'Стиральные машины'
db=R/'baseline.sqlite3'
assert not db.exists()
w=Workbook();s=w.active;s.append(['Бренд','Артикул','Наименование','Категория'])
s.append(['Electrolux',model,'Electrolux '+model,category]);w.save(R/'baseline_input.xlsx')
p=importer.preview_xlsx(R/'baseline_input.xlsx').products[0]
jobs.initialize(db);discovery_trace.initialize(db)
with sqlite3.connect(db) as c:
 c.execute("INSERT INTO batches VALUES ('el78','baseline_input.xlsx','Sheet','{}','2026-10-11')")
 c.execute("INSERT INTO products (id,batch_id,row_number,name,brand,search_code,alternate_code,category,needs_confirmation,issues_json,original_values_json) VALUES (1,'el78',?,?,?,?,?,?,0,'[]',?)",(p.row_number,p.name,p.brand,p.search_code,p.alternate_code,p.category,json.dumps(p.original_values,ensure_ascii=False)))
jid=jobs.enqueue(db,1,[1,2,3,4,6]);start=time.monotonic();worker.run_once(db)
out={'origin':'unmodified ordinary run_once; no Electrolux adapter/known PDP injection','input':{'article':p.search_code,'name':p.name,'category':p.category},'seconds':time.monotonic()-start,'job':jobs.list_jobs(db,1)[0],'sources':jobs.get_source_pages(db,1),'facts':jobs.get_facts(db,1),'photos':jobs.get_photo_candidates(db,1,include_excluded=True),'documents':jobs.get_documents(db,1),'readiness':readiness.card_readiness(db,1),'trace':discovery_trace.for_job(db,jid)}
(R/'baseline.json').write_bytes((json.dumps(out,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
print(json.dumps({'job':out['job'],'readiness':out['readiness']},ensure_ascii=False))
