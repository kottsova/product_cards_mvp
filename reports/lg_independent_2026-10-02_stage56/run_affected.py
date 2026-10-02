from __future__ import annotations
import json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from product_tool import jobs, worker
from product_tool.readiness import card_readiness
HERE=Path(__file__).resolve().parent
DB=ROOT/"data/stage56/stage56.sqlite3"
OUT=HERE/"affected_rerun.json"
ARTICLES=("43NANO756QA_KZ","WZ09AWN")
def snapshot(pid):
    pages=jobs.get_source_pages(DB,pid)
    docs=jobs.get_documents(DB,pid)
    photos=jobs.get_photo_candidates(DB,pid,include_excluded=False)
    return {
        "pages":[{"source_key":x["source_key"],"url":x["url"],"match_level":x["match_level"],"error":x["error"]} for x in pages],
        "documents":[{"source_key":x["source_key"],"direct_url":x["direct_url"]} for x in docs],
        "photos":[{"source_key":x["source_key"],"url":x["url"],"selected":x["selected"]} for x in photos],
        "readiness":card_readiness(DB,pid),
    }
def main():
    if OUT.exists():raise SystemExit("Already run")
    first=json.loads((HERE/"first_pass.json").read_text(encoding="utf8"))
    rows=[]
    for article in ARTICLES:
        row=next(x for x in first["rows"] if x["article"]==article)
        pid=row["product_id"]
        before=snapshot(pid)
        jid=jobs.enqueue(DB,pid,[1,2,3,4,6])
        print("START",article,jid,flush=True)
        if not worker.run_once(DB):raise RuntimeError("No job")
        after=snapshot(pid)
        current=jobs.list_jobs(DB,pid)[0]
        entry={"article":article,"product_id":pid,"job_id":jid,"before":before,"after":after,
               "job_status":current["status"],"job_message":current["message"]}
        rows.append(entry)
        print("DONE",article,current["status"],after["readiness"]["verdict"],flush=True)
        OUT.write_text(json.dumps(rows,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
if __name__=="__main__":main()
