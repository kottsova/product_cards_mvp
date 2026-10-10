"""Stage 72: unmodified ordinary worker baseline, no injected adapters/URLs."""
import sys, json, sqlite3, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from product_tool import jobs, worker, readiness, resolution

ROOT = Path(__file__).resolve().parent
db = ROOT / 'baseline.sqlite3'
if db.exists():
    raise RuntimeError('Never overwrite a baseline database')
jobs.initialize(db)
with sqlite3.connect(db) as c:
    c.execute("INSERT INTO batches (id,filename,sheet_name,mapping_json,confirmed_at) VALUES ('baseline','baseline.xlsx','Products','{}','2026-10-10')")
    c.execute("INSERT INTO products (batch_id,row_number,name,brand,search_code,alternate_code,category,needs_confirmation,issues_json,original_values_json) VALUES ('baseline',2,'HyperX QuadCast 2 S Black','HyperX','9A273AA','','Микрофоны',0,'[]','{}')")
jobs.enqueue(db, 1, [1,2,3,4,6])
start=time.monotonic()
processed=worker.run_once(db)
result={'mode':'actual live ordinary run_once; pre-change; no injected adapter', 'input':jobs.get_product(db,1), 'processed':processed,'elapsed':time.monotonic()-start,'jobs':jobs.list_jobs(db,1),'sources':jobs.get_source_pages(db,1),'facts':jobs.get_facts(db,1),'photos':jobs.get_photo_candidates(db,1,include_excluded=True),'documents':jobs.get_documents(db,1),'readiness':readiness.card_readiness(db,1)}
(ROOT/'baseline.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:result[k] for k in ('mode','elapsed','processed','readiness')},ensure_ascii=False))
print([(s['source_key'],s['match_level'],s['url'],s['error']) for s in result['sources']])
