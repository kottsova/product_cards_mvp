"""Read-only, post-run Stage 56 evidence harvest. Never runs the worker."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))

from product_tool import discovery_trace, jobs, manual_status, readiness, storage
from product_tool.adapters.lg import lg_article_components, lg_base_model
from product_tool.lg_identity import photo_tied_to_article
from product_tool.lg_sitemap_discovery import model_keys
from product_tool.worker import _lg_model_candidates_from_name

HERE=Path(__file__).resolve().parent
DB=ROOT/"data/stage56/stage56.sqlite3"
DATASET=HERE/"dataset.json"
OUT=HERE/"first_pass.json"
TRACE=HERE/"first_pass_trace.json"

def main():
    if OUT.exists() or TRACE.exists():
        raise SystemExit("First-pass harvest exists; refusing to replace it")
    expected=(HERE/"dataset.sha256").read_text(encoding="ascii").split()[0]
    if hashlib.sha256(DATASET.read_bytes()).hexdigest()!=expected:
        raise SystemExit("Frozen dataset hash changed")
    manifest=json.loads((HERE/"first_pass_manifest.json").read_text(encoding="utf-8"))
    if manifest["dataset_sha256"]!=expected:
        raise SystemExit("Manifest does not match frozen dataset")
    rows=[]
    traces={}
    for item in manifest["rows"]:
        pid=item["id"]
        product=jobs.get_product(DB,pid)
        job=jobs.list_jobs(DB,pid)[0]
        if job["status"] not in {"done","needs_review","error","not_found"}:
            raise SystemExit(f"Job unfinished: {item['search_code']} {job['status']}")
        sources=jobs.get_source_pages(DB,pid)
        facts=jobs.get_facts(DB,pid)
        resolved=jobs.get_resolved(DB,pid)
        photos=jobs.get_photo_candidates(DB,pid)
        documents=jobs.get_documents(DB,pid)
        try: trace=discovery_trace.for_job(DB,job["id"])
        except sqlite3.OperationalError: trace=[]
        traces[product["search_code"]]=trace
        queries=[{"provider":x.get("provider"),"query":x.get("query"),"url":x.get("url")}
                 for x in trace if x.get("event")=="query"]
        source_rows=[{k:s[k] for k in ("source_key","site_name","url","found_model","match_level","evidence","error")}
                     for s in sources]
        ready=readiness.card_readiness(DB,pid)
        confirmed_facts=sum(bool(x["selected_value"]) and bool(x["full_sku_confirmed"]) and not x["conflict"] for x in resolved)
        confirmed_photos=sum(bool(x["selected"]) and photo_tied_to_article(x,sources) for x in photos if x["kind"]!="excluded")
        source_counts=Counter(x["source_key"] for x in facts)
        photo_counts=Counter(x["source_key"] for x in photos if x["kind"]!="excluded")
        rows.append({
            "product_id":pid,"article":product["search_code"],"category":product["category"],
            "catalog_name":product["name"],"job_id":job["id"],"job_status":job["status"],
            "job_message":job["message"],"readiness":ready["verdict"],
            "blocking_gaps":ready["blocking_gaps"],"advisory_gaps":ready["advisory_gaps"],
            "model_variants":{"components":lg_article_components(product["search_code"]),
                              "base":lg_base_model(product["search_code"]),
                              "from_name":_lg_model_candidates_from_name(product["name"],product["search_code"]),
                              "sitemap_keys":model_keys(product["search_code"])},
            "queries":queries,"sources":source_rows,
            "official_exact_regions":ready["official_exact_regions"],
            "raw_facts":len(facts),"facts_by_source":dict(source_counts),
            "confirmed_characteristics":confirmed_facts,
            "official_facts_from_exact_pages":ready["official_facts_from_exact_pages"],
            "photo_candidates":len(photos),"photos_by_source":dict(photo_counts),
            "confirmed_photos":confirmed_photos,
            "official_gallery_from_exact_pages":ready["official_gallery_from_exact_pages"],
            "documents":[{k:d[k] for k in ("source_key","title","language","direct_url","source_url")} for d in documents],
            "manual_status":manual_status.russian_status(DB,pid,product["search_code"]),
            "real_conflicts":ready["real_conflicts"],
            "main_gap":next(iter(ready["blocking_gaps"]),""),
            "trace_events":len(trace),
            "job_events":[{k:e[k] for k in ("stage","level","message","source_url")} for e in jobs.list_events(DB,job["id"])]
        })
    with storage._connection(DB) as connection:
        integrity=connection.execute("PRAGMA integrity_check").fetchone()[0]
        fk=len(connection.execute("PRAGMA foreign_key_check").fetchall())
    payload={"frozen_dataset_sha256":expected,"batch_id":manifest["batch_id"],
             "product_count":len(rows),"job_count":sum(1 for x in rows if x["job_id"]),
             "sqlite_integrity":integrity,"foreign_key_violations":fk,"rows":rows}
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    TRACE.write_text(json.dumps(traces,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("HARVESTED",len(rows),"integrity",integrity,"fk",fk)

if __name__=="__main__":
    main()
