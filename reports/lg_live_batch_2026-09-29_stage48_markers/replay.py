"""Replay only LG rows with observed marker value cells from saved HTML."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from bs4 import BeautifulSoup
from product_tool import jobs, storage
from product_tool.adapters.lg import extract_lg_attributes, extract_lg_ru_attributes
from product_tool.fetch_history import latest_source_snapshot
from product_tool.normalization import normalize_facts
from product_tool.readiness import card_readiness

BATCH="ae3d2cb381744ba8a811e54231233254"
IDS=(5,9,10,12,14,15)

def replay(path: Path, add_jobs: bool) -> list[dict]:
    jobs.initialize(path)
    report=[]
    for pid in IDS:
        product=jobs.get_product(path,pid)
        assert product and product["batch_id"]==BATCH and product["brand"].strip().casefold()=="lg"
        old=jobs.get_resolved(path,pid)
        prior=jobs.list_jobs(path,pid)[0]
        for source,extractor in (("lg_kz",extract_lg_attributes),("lg_ru",extract_lg_ru_attributes)):
            page=next((p for p in jobs.get_source_pages(path,pid) if p["source_key"]==source),None)
            snap=latest_source_snapshot(path,pid,source)
            if not page or not snap or not snap["content"] or page["url"]!=snap["source_url"]:
                continue
            assert hashlib.sha256(snap["content"].encode("utf8")).hexdigest()==snap["content_sha256"]
            raw=extractor(BeautifulSoup(snap["content"],"html.parser"))
            normalized=normalize_facts(raw)
            with storage._connection(path) as c:
                c.execute("DELETE FROM extracted_attribute_facts WHERE product_id=? AND source_key=?",(pid,source))
                c.executemany("""INSERT INTO extracted_attribute_facts
                    (product_id,source_page_id,source_key,site_name,raw_name,raw_value,section,value_cell,normalized_name,normalized_value,unit)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    [(pid,page["id"],source,page["site_name"],f.raw_name,f.raw_value,f.section,
                      None if f.value_cell is None else int(f.value_cell),
                      f.normalized_name,f.normalized_value,f.unit) for f in normalized])
        jobs.resolve_product(path,pid)
        rows=jobs.get_resolved(path,pid)
        pages=jobs.get_source_pages(path,pid)
        conflicts=sum(bool(r["conflict"]) for r in rows)
        confirmed=sum(bool(r["full_sku_confirmed"]) and not bool(r["conflict"]) for r in rows)
        exact=any(p["source_key"] in ("lg_kz","lg_ru") and p["match_level"]=="full_sku" and not p["error"] for p in pages)
        supplier=any(p["source_key"]=="sulpak" and p["match_level"]=="full_sku" for p in pages)
        status="needs_review" if conflicts or not (exact or supplier) else "done"
        if pages and all(p["error"] for p in pages):status="error"
        card=card_readiness(path,pid)
        if add_jobs:
            now=storage._now(); job_id=f"stage48-markers-offline-{pid}"
            with storage._connection(path) as c:
                c.execute("""INSERT INTO search_jobs
                    (id,product_id,stages_json,status,current_stage,message,created_at,updated_at,started_at,finished_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    (job_id,pid,"[3]",status,3,
                     f"Offline LG marker/value-cell replay from saved HTML; confirmed specs={confirmed}, conflicts={conflicts}; card={card['verdict']}.",
                     now,now,now,now))
                c.execute("""INSERT INTO job_events (job_id,stage,level,message,created_at)
                    VALUES (?,?,?,?,?)""",
                    (job_id,3,"info" if status=="done" else "warning",
                     f"Saved LG snapshot only; previous job {prior['id']}; no source request.",now))
        report.append({"id":pid,"sku":product["search_code"],
            "before":{"job":prior["status"],"conflicts":sum(bool(r["conflict"]) for r in old),
                      "confirmed":sum(bool(r["full_sku_confirmed"]) and not bool(r["conflict"]) for r in old)},
            "after":{"job":status,"conflicts":conflicts,"confirmed":confirmed,"verdict":card["verdict"]},
            "conflict_names":[r["normalized_name"] for r in rows if r["conflict"]]})
    return report

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("database",type=Path)
    ap.add_argument("--add-jobs",action="store_true")
    args=ap.parse_args()
    print(json.dumps(replay(args.database,args.add_jobs),ensure_ascii=True,indent=2))

