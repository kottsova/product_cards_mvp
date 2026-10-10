"""Unmodified production run_once baseline followed by separate official diagnosis."""
import sys,json,sqlite3,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from openpyxl import Workbook
from product_tool import jobs,worker,readiness,importer,discovery_trace
from product_tool.adapters.policy_session import PolicyAwareSession,record_responses
from product_tool.adapters.published_page import published_links
R=Path(__file__).parent;O=R/'baseline';O.mkdir(exist_ok=True);db=O/'live.sqlite3'
assert not db.exists()
w=Workbook();s=w.active;s.title='Products';s.append(['Бренд','Артикул','Наименование','Категория']);s.append(['Dreame','H14 Pro','Dreame H14 Pro [region=Global]','Вертикальные моющие пылесосы']);w.save(O/'input.xlsx')
p=importer.preview_xlsx(O/'input.xlsx');jobs.initialize(db);discovery_trace.initialize(db)
with sqlite3.connect(db) as c:
 c.execute("INSERT INTO batches VALUES ('dr76baseline','input.xlsx','Products','{}','2026-10-11')")
 for i,x in enumerate(p.products,1):c.execute("INSERT INTO products (id,batch_id,row_number,name,brand,search_code,alternate_code,category,needs_confirmation,issues_json,original_values_json) VALUES (?,'dr76baseline',?,?,?,?,?,?,0,'[]',?)",(i,x.row_number,x.name,x.brand,x.search_code,x.alternate_code,x.category,json.dumps(x.original_values,ensure_ascii=False)))
with record_responses(O/'http'):
 j=jobs.enqueue(db,1,[1,2,3,4,6]);worker.run_once(db)
 result={'baseline_commit':'74df7eabc75865774d0b09ffc2ca24b2b0d4d175','input':p.to_dict(),'supplier_sku':None,'query_variants':['H14 PRO'],'job':jobs.list_jobs(db,1)[0],'events':jobs.list_events(db,j),'sources':jobs.get_source_pages(db,1),'specs':jobs.get_facts(db,1),'photos':jobs.get_photo_candidates(db,1),'manuals':jobs.get_documents(db,1),'readiness':readiness.card_readiness(db,1),'trace':discovery_trace.for_job(db,j)}
 (O/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
 http=PolicyAwareSession(O/'official_diagnostic_log.json',allowed_hosts=('dreametech.com','dreame.tech'))
 home=http.get('https://global.dreametech.com/',timeout=15)
 if not home.ok or home.marker:
  result['separate_official_diagnostic']={'url':home.url,'status':home.status_code,'marker':home.marker,'not_used_by_baseline_worker':True}
  (O/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');sys.exit(0)
 (O/'homepage.html').write_text(home.text,encoding='utf8')
 links=published_links(home.text,home.url);u=next(u for u,t in links if t.strip().casefold()=='h14 pro' and '/products/' in u)
 page=http.get(u,timeout=15);(O/'pdp.html').write_text(page.text,encoding='utf8')
 result['separate_official_diagnostic']={'provider':'published_homepage_href','url':u,'status':page.status_code,'marker':page.marker,'sha256':hashlib.sha256(page.text.encode()).hexdigest(),'not_used_by_baseline_worker':True,'support_urls':[(u,t) for u,t in links if 'manual' in t.casefold()]}
 (O/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
 print(json.dumps({'job':result['job']['status'],'specs':len(result['specs']),'photos':len(result['photos']),'ready':result['readiness']['verdict'],'official_diagnostic':result['separate_official_diagnostic']},ensure_ascii=False),flush=True)
