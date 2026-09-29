"""Stage 42: reclassify saved LG product pages, preserve every fetch and card."""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path
from bs4 import BeautifulSoup
from product_tool import jobs
from product_tool.adapters.lg import _product_designation
from product_tool.adapters.sulpak import _stopped_host_evidence
from product_tool.adapters.lg_policy import lg_log_path

BATCH = "ae3d2cb381744ba8a811e54231233254"
KIT = "P12ED.NSAR + P12ED.USAR"
FRIDGE = "GC-B459MLWM.ADSQCIS"
NOTE = (" Страница поддержки по ссылке этой RU-карточки перенаправила на базовую модель GC-B459MLWM. "
        "Связанный с ней PDF проверен по содержимому: это русское руководство (40 страниц), "
        "но в тексте не названы GC-B459MLWM и GC-B459MLWM.ADSQCIS. "
        "Ссылка https://gscs-b2c.lge.com/open/downloadFile?fileId=CXgdWUo44amDWnMThA21pA сохранена как кандидат; инструкция полного артикула не подтверждена.")

def apply(path: Path) -> None:
    with sqlite3.connect(path) as db:
        db.row_factory = sqlite3.Row
        rows = db.execute("SELECT id,search_code FROM products WHERE batch_id=? AND search_code IN (?,?)", (BATCH,KIT,FRIDGE)).fetchall()
        product_ids = {row["search_code"]: row["id"] for row in rows}
        assert set(product_ids) == {KIT,FRIDGE}, product_ids
        kit_id, fridge_id = product_ids[KIT], product_ids[FRIDGE]
        blocked = db.execute("SELECT id,url,error FROM source_pages WHERE product_id=? AND source_key='sulpak'",(kit_id,)).fetchone()
        assert blocked and "policy_host_stopped" in blocked["error"] and "p12ed" in blocked["url"]
        evidence = _stopped_host_evidence(type("Logged",(),{"log_path":lg_log_path(Path("data"))})(),blocked["url"])
        assert "s3wer" in evidence.lower() and "не отправлялся" in evidence
        db.execute("UPDATE source_pages SET evidence=?,error=? WHERE id=?", (evidence,"policy_host_stopped: candidate page not requested",blocked["id"]))
        for source_key,region in (("lg_kz","kz"),("lg_ru","ru")):
            snap = db.execute("SELECT content,source_url FROM source_snapshots WHERE product_id=? AND source_id=? AND length(content)>0 ORDER BY id DESC LIMIT 1",(fridge_id,source_key)).fetchone()
            page = db.execute("SELECT id,url FROM source_pages WHERE product_id=? AND source_key=?",(fridge_id,source_key)).fetchone()
            assert snap and page and snap["source_url"] == page["url"]
            found,level,proof = _product_designation(BeautifulSoup(snap["content"],"html.parser"),FRIDGE,"GC-B459MLWM",region=region)
            assert found == FRIDGE and level == "full_sku", (source_key,found,level)
            if region == "ru":
                proof += NOTE
            db.execute("UPDATE source_pages SET found_model=?,match_level=?,evidence=? WHERE id=?",(found,level,proof,page["id"]))
        db.commit()
    jobs.resolve_product(path,fridge_id)

if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("database",type=Path)
    apply(parser.parse_args().database)
