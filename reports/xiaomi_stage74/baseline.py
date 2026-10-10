"""Ordinary worker baseline before Xiaomi dispatch/parser additions."""
import sys,json,sqlite3
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from product_tool import jobs,worker,readiness,discovery_trace
R=Path(__file__).parent;db=R/'baseline.sqlite3';assert not db.exists();jobs.initialize(db);discovery_trace.initialize(db)
p={'article':'Xiaomi 14','name':'Xiaomi 14 [RAM=12GB;storage=256GB;color=Black;region=Global]','brand':'Xiaomi','category':'Смартфоны','article_kind':'marketing model search identifier, not claimed retail SKU','model_number':'unknown before official relation','retail_sku':'unknown','generation':'14','official_pdp_observed_separately':'https://www.mi.com/global/product/xiaomi-14/'}
with sqlite3.connect(db) as c:
 c.execute("INSERT INTO batches VALUES ('xm74baseline','Xiaomi baseline.xlsx','Products','{}','2026-10-10')")
 pid=c.execute("INSERT INTO products (batch_id,row_number,name,brand,search_code,alternate_code,category,needs_confirmation,issues_json,original_values_json) VALUES ('xm74baseline',2,?,?,?,'',?,0,'[]',?)",(p['name'],p['brand'],p['article'],p['category'],json.dumps(p))).lastrowid
jid=jobs.enqueue(db,pid,[1,2,3,4,6]);worker.run_once(db)
out={'origin':'ordinary actual worker.run_once, no Xiaomi adapter/factory or seeded URL','input':p,'job':jobs.list_jobs(db,pid)[0],'sources':jobs.get_source_pages(db,pid),'facts':jobs.get_facts(db,pid),'photos':jobs.get_photo_candidates(db,pid),'documents':jobs.get_documents(db,pid),'readiness':readiness.card_readiness(db,pid),'trace':discovery_trace.for_job(db,jid)}
(R/'baseline.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8');print(out['job']['status'],out['readiness']['verdict'],len(out['facts']),len(out['photos']))
