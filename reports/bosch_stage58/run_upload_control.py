"""Production Excel-upload round trip for the Stage 58 control article."""
from pathlib import Path
import io
from openpyxl import Workbook,load_workbook
from fastapi.testclient import TestClient
from product_tool import jobs,storage,worker,bosch_readiness
from product_tool.web import create_app
root=Path('reports/bosch_stage58/upload_control');root.mkdir(exist_ok=True)
db=root/'batches.sqlite3'
if db.exists():raise SystemExit('upload control already exists')
book=Workbook();sheet=book.active;sheet.title='Products'
sheet.append(['Category','Brand','Name','Seller code','Model'])
sheet.append(['Варочные панели','BOSCH','Варочная панель индукционная 60 см, PUE611BB5E','PUE611BB5E',''])
stream=io.BytesIO();book.save(stream);book.close()
with TestClient(create_app(root,start_worker=False)) as client:
 upload=client.post('/upload',files={'file':('bosch_stage58.xlsx',stream.getvalue(),'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')},follow_redirects=False)
 assert upload.status_code==303,(upload.status_code,upload.text[:300])
 confirm=client.post(upload.headers['location']+'/confirm',data={'brand_2':'BOSCH','search_code_2':'PUE611BB5E','alternate_code_2':'','category_2':'Варочные панели'},follow_redirects=False)
 assert confirm.status_code==303,(confirm.status_code,confirm.text[:300])
 batch_id=confirm.headers['location'].rsplit('/',1)[-1]
 pid=storage.get_batch(db,batch_id)['products'][0]['id']
 start=client.post(f'/products/{pid}/search',data={'stages':['1','2','3','4','6']},follow_redirects=False)
 assert start.status_code==303,(start.status_code,start.text[:300])
 assert worker.run_once(db)
 job=jobs.list_jobs(db,pid)[0]
 page=client.get(f'/products/{pid}')
 export=client.get(f'/batches/{batch_id}/export.xlsx')
 ready=bosch_readiness.card_readiness(db,pid)
 print('upload',upload.status_code,'confirm',confirm.status_code,'job',job['status'],'readiness',ready['verdict'],'page',page.status_code,'export',export.status_code,'xlsx_bytes',len(export.content))
 assert job['status']=='done' and ready['verdict']=='export_ready'
 assert page.status_code==200 and export.status_code==200
