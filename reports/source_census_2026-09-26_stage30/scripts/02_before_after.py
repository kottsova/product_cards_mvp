"""Stage 30 step 2 -- OFFLINE. Before (Stage 28 record of 15 cards + Stage 29 record of 4 cards, both as produced by the code of that time) against after (raw/all19_result.json, Stage 30 code): variant, document,
dealer link request, job status and readiness for each checked Samsung card.

Output: raw/before_after.json (every card, changed or not) and a short table on stdout.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
STAGE = HERE.parent
sys.path.insert(0, str(ROOT))

LEVEL = {"full_sku": "полный артикул", "code_in_page_text": "код только в тексте", "base_model": "базовая модель", "none": "нет страницы"}


def summary(card: dict, source: str) -> dict:
    r = card["readiness"]
    ins = r["instruction"]
    dns = card["sources"].get("dns", {})
    basis = ins.get("acceptance_basis")
    if not ins["saved"]:
        document = "нет файла"
    elif ins["russian_saved"] and ins.get("accepted"):
        document = "русская инструкция принята"
    elif ins["russian_saved"]:
        document = f"русский файл не принят ({basis})"
    elif ins.get("brief_guides"):
        pages = ", ".join(str(n) for b in ins["brief_guides"] for n in b["pages"])
        document = f"краткая памятка, русский раздел стр. {pages}; не полная инструкция"
    else:
        document = "файл не на русском"
    return {"category": card["category"], "article": card["article"], "source": source, "variant": LEVEL.get(r["page_match_level"], r["page_match_level"]), "document": document, "document_basis": basis,
            "dealer_link_request": "запрос сформирован" if dns.get("match_level") == "dealer_url_needed" else "не формируется" if dns.get("match_level") == "not_needed" else dns.get("match_level", ""),
            "job_status": card["job_status"], "verdict": r["verdict"], "blocking_gaps": r["blocking_gaps"], "advisory_gaps": r["advisory_gaps"], "photos_selected": r["official_photos_selected"], "photos_found": r["official_photos"]}


def main() -> None:
    before_cards = json.loads((ROOT / "reports/source_census_2026-09-26_stage28/raw/all15_result.json").read_text(encoding="utf-8"))["cards"]
    before = {c["article"]: summary(c, "Stage 28 (15 cards)") for c in before_cards}
    for c in json.loads((ROOT / "reports/source_census_2026-09-26_stage29/raw/batch5a_result.json").read_text(encoding="utf-8"))["cards"]:
        before[c["article"]] = summary(c, "Stage 29 real run")
    after_cards = json.loads((STAGE / "raw/all19_result.json").read_text(encoding="utf-8"))["cards"]
    after = {c["article"]: summary(c, "Stage 30 offline") for c in after_cards}
    rows = []
    for article, a in after.items():
        b = before[article]
        changed = [k for k in ("variant", "document", "dealer_link_request", "job_status", "verdict", "blocking_gaps", "photos_selected") if a[k] != b[k]]
        rows.append({"article": article, "category": a["category"], "changed": changed, "before": b, "after": a})
    (STAGE / "raw/before_after.json").write_text(json.dumps({"cards": rows}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for row in rows:
        if row["changed"]:
            b, a = row["before"], row["after"]
            print(f"{row['category']} ({row['article']}): changed={row['changed']}")
            for key in row["changed"]:
                print(f"   {key}: {b[key]} -> {a[key]}")
    print("unchanged:", [r["category"] for r in rows if not r["changed"]])


if __name__ == "__main__":
    main()
