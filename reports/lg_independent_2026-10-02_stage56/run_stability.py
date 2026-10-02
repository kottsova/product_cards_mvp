from __future__ import annotations
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from product_tool import jobs,worker
from product_tool.readiness import card_readiness
HERE=Path(__file__).resolve().parent
DB=ROOT/"data/stage56/stage56.sqlite3"
OUT=HERE/"stability_rerun.json"
ARTICLES=("32LB650B6LA","DC90V9V9WN","GC-B399SMCL.APZQCIS","MS2535GIS","S70TY.ARUSLLK")
def snapshot(pid):
 pages=jobs.get_source_pages(DB,pid)
 docs=jobs.get_documents(DB,pid)
 photos=jobs.get_photo_candidates(DB,pid,include_excluded=False)
 return {"exact_pages":sorted((p["source_key"],p["url"]) for p in pages if p["match_level"]=="full_sku" and not p["error"] and p["url"]),
  "documents":sorted((d["source_key"],d["direct_url"]) for d in docs),
  "selected_photos":sorted((p["source_key"],p["url"]) for p in photos if p["selected"]),
  "photo_candidates":sorted((p["source_key"],p["url"]) for p in photos),
  "readiness":card_readiness(DB,pid),
  "duplicate_documents":len(docs)-len({(d["source_key"],d["direct_url"]) for d in docs}),
  "duplicate_photos":len(photos)-len({(p["source_key"],p["url"]) for p in photos})}
def main():
 if OUT.exists():raise SystemExit("Already run")
 first=json.loads((HERE/"first_pass.json").read_text(encoding="utf8"))
 records=[]
 for article in ARTICLES:
  row=next(r for r in first["rows"] if r["article"]==article)
  pid=row["product_id"]; before=snapshot(pid)
  jid=jobs.enqueue(DB,pid,[1,2,3,4,6])
  print("START",article,jid,flush=True)
  if not worker.run_once(DB):raise RuntimeError("No job")
  after=snapshot(pid)
  lost={key:sorted(set(map(tuple,before[key]))-set(map(tuple,after[key]))) for key in ("exact_pages","documents","selected_photos")}
  status=jobs.list_jobs(DB,pid)[0]["status"]
  record={"article":article,"product_id":pid,"job_id":jid,"status":status,"before":before,"after":after,"lost":lost}
  records.append(record)
  OUT.write_text(json.dumps(records,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
  print("DONE",article,status,after["readiness"]["verdict"],"lost",sum(map(len,lost.values())),flush=True)
if __name__=="__main__":main()
