"""Stage 49: offline identity replay for only affected rows in the existing LG batch."""
from __future__ import annotations
import argparse, gzip, hashlib, json, sqlite3, tempfile
from contextlib import closing
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from bs4 import BeautifulSoup
from product_tool import jobs, storage
from product_tool.adapters.lg import _product_designation, _support_page_sales_code
from product_tool.fetch_history import latest_source_snapshot
from product_tool.lg_identity import structured_sales_relation
from product_tool.readiness import card_readiness

ROOT=Path(__file__).resolve().parents[2]
BATCH="ae3d2cb381744ba8a811e54231233254"
BEFORE_HASH="8fa671efe7feb2794343af7fcdcc11a765736703c396f340436223dcfee51155"
SAVED_SUPPORT={
  10:("reports/lg_live_batch_2026-09-28_stage43/step3b_data/raw/003_3feb3be362.gz",
      "3feb3be36270fdcc7c8b33933c4e2770d8b90a5f718852c833c6257c8504244f",
      "https://www.lg.com/ru/support/product/lg-W4W8LVPKZHM"),
  15:("reports/lg_live_batch_2026-09-28_stage43/step3b_data/raw/007_1935ac5e38.gz",
      "1935ac5e387377d1b338cb8f7666ca41a2738b138e3d0bcf8d3a6ba7b54f3b78",
      "https://www.lg.com/ru/support/product/lg-ON77DK"),
}

def summary(db, pid):
    product=jobs.get_product(db,pid)
    r=card_readiness(db,pid)
    rows=jobs.get_resolved(db,pid)
    return {"id":pid,"article":product["search_code"],
            "job":jobs.list_jobs(db,pid)[0]["status"],"card":r["verdict"],
            "gaps":r["blocking_gaps"],"confirmed_specs":sum(bool(x["full_sku_confirmed"]) and not x["conflict"] for x in rows),
            "exact_gallery":r["official_gallery_from_exact_pages"],
            "manual_file_found":r["instruction"]["russian_file_found"],
            "manual_tied":r["instruction"]["russian"]}

def replay(db:Path,*,apply:bool):
    if apply:
        assert db.resolve()==(ROOT/'data/batches.sqlite3').resolve()
        assert hashlib.sha256(db.read_bytes()).hexdigest()==BEFORE_HASH,"working DB changed since backup; stop"
    before=[summary(db,p) for p in (4,10,12,15)]
    for key,region in (("lg_kz","kz"),("lg_ru","ru")):
        snap=latest_source_snapshot(db,15,key)
        assert snap and snap["source_url"] and snap["content"]
        assert hashlib.sha256(snap["content"].encode('utf8')).hexdigest()==snap["content_sha256"]
        found,level,evidence=_product_designation(BeautifulSoup(snap["content"],"html.parser"),"ON77DKDRUSLLK","ON77DK",region=region)
        assert (found,level)==("ON77DKDRUSLLK","full_sku")
        with storage._connection(db) as c:
            row=c.execute("SELECT id,url FROM source_pages WHERE product_id=15 AND source_key=?",(key,)).fetchone()
            assert row and row["url"]==snap["source_url"]
            c.execute("UPDATE source_pages SET found_model=?,match_level=?,evidence=? WHERE id=?",(found,level,evidence+f" Offline verified snapshot {snap['id']} sha256={snap['content_sha256']}.",row["id"]))
    for pid,(rel,expected,url) in SAVED_SUPPORT.items():
        article=jobs.get_product(db,pid)["search_code"]
        raw=gzip.open(ROOT/rel,'rb').read()
        digest=hashlib.sha256(raw).hexdigest()
        html=raw.decode('utf8')
        assert digest==expected
        printed=_support_page_sales_code(html)
        relation=structured_sales_relation(article,printed)
        level="full_sku" if relation=="exact" else "base_model" if relation in {"regional_variant_of","family_of"} else "unknown"
        assert (pid,relation)==((10,"exact") if pid==10 else (15,"regional_variant_of"))
        evidence=f"Offline replay of saved official support response {rel}; sha256={digest}; printed data-product-id={printed}; relation={relation}. URL alone is not evidence."
        with storage._connection(db) as c:
            c.execute('''INSERT INTO source_pages (product_id,source_key,site_name,url,found_model,match_level,evidence,fetched_at,error,description,photos_json)
                         VALUES (?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(product_id,source_key) DO UPDATE SET
                         site_name=excluded.site_name,url=excluded.url,found_model=excluded.found_model,
                         match_level=excluded.match_level,evidence=excluded.evidence,fetched_at=excluded.fetched_at,
                         error=excluded.error,description=excluded.description,photos_json=excluded.photos_json''',
                      (pid,'lg_ru_support','LG RU support',url,printed,level,evidence,'2026-09-28T00:00:00+00:00','','','[]'))
    jobs.resolve_product(db,15)
    for pid in (10,12,15):
        product=jobs.get_product(db,pid); assert product and product["batch_id"]==BATCH
        pages=jobs.get_source_pages(db,pid); counts=jobs.result_counts(db,pid)
        exact=any(x["source_key"] in {"lg_kz","lg_ru"} and x["match_level"]=="full_sku" and not x["error"] for x in pages)
        status="done" if exact and not counts["conflicts"] else "needs_review"
        card=card_readiness(db,pid)
        prior=jobs.list_jobs(db,pid)[0]
        now=storage._now(); job_id=f"stage49-offline-{pid}"
        with storage._connection(db) as c:
            assert not c.execute("SELECT 1 FROM search_jobs WHERE id=?",(job_id,)).fetchone()
            message=f"Offline LG identity replay from saved official content; product exact={exact}; conflicts={counts['conflicts']}; card={card['verdict']}; gaps={','.join(card['blocking_gaps'])}."
            c.execute('''INSERT INTO search_jobs (id,product_id,stages_json,status,current_stage,message,created_at,updated_at,started_at,finished_at)
                         VALUES (?,?,?,?,?,?,?,?,?,?)''',(job_id,pid,'[1,2,3,4,6]',status,6,message,now,now,now,now))
            c.execute('''INSERT INTO job_events (job_id,stage,level,message,created_at) VALUES (?,?,?,?,?)''',
                      (job_id,6,'info' if status=='done' else 'warning',f"Offline identity evaluation; preceding job {prior['id']}; no network request.",now))
    after=[summary(db,p) for p in (4,10,12,15)]
    with storage._connection(db) as c:
        integrity=c.execute('PRAGMA integrity_check').fetchone()[0]
        foreign=c.execute('PRAGMA foreign_key_check').fetchall()
        products=c.execute('SELECT count(*) FROM products WHERE batch_id=?',(BATCH,)).fetchone()[0]
        active=c.execute("SELECT count(*) FROM search_jobs WHERE status IN ('queued','running')").fetchone()[0]
    assert integrity=='ok' and not foreign and products==12 and active==0
    return {"before":before,"after":after,"integrity":integrity,"foreign_key_violations":len(foreign),"products":products,"active_jobs":active}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('database',type=Path);parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    if args.apply:
        result=replay(args.database,apply=True)
    else:
        # Default is read-only for the supplied database: replay on a SQLite
        # backup in a temporary directory, never in-place.
        with tempfile.TemporaryDirectory() as directory:
            copy=Path(directory)/"dryrun.sqlite3"
            with closing(sqlite3.connect(args.database)) as source, closing(sqlite3.connect(copy)) as target:
                source.backup(target)
            result=replay(copy,apply=False)
    print(json.dumps(result,ensure_ascii=False,indent=2))
