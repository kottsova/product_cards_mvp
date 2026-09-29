"""Stage 28 step 7 -- OFFLINE. Records the content assessment of the dishwasher's Russian instruction (obtained in step 2) in product_tool/config/samsung_recorded_documents.v1.json, so the ordinary
path uses it for the same link and article WITHOUT downloading the 47 MB file again (the adapter's default cap stays 40 MB). The tie to the CURRENT page is still read live.

Idempotent: an entry for the same article and link is replaced.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
STAGE = HERE.parent


def main() -> None:
    result = json.loads((STAGE / "raw/dishwasher_result.json").read_text(encoding="utf-8"))
    declaration = json.loads((STAGE / "raw/dishwasher_declaration.json").read_text(encoding="utf-8"))
    assessed = next(f for f in result["files"] if f.get("facts"))
    facts = {k: v for k, v in assessed["facts"].items() if k not in ("acceptance", "tied_by_official_page", "assessed_from")}
    extract = json.loads((STAGE / "docs_extract/index.json").read_text(encoding="utf-8"))[0]
    entry = {
        "article": "DW60M5050BB/WT", "href": declaration["candidate"]["href"], "final_url": assessed["final_url"], "bytes": extract["bytes"], "pages": extract["pages"],
        "assessed": f"{result['finished_at'][:10]} (Stage 28): the file (47 MB, ceiling 60 MB, 1 request) was read page by page with pypdf; the bytes were not kept",
        "evidence": ["reports/source_census_2026-09-26_stage28/raw/dishwasher_result.json", "reports/source_census_2026-09-26_stage28/raw/dishwasher_declaration.json", "reports/source_census_2026-09-26_stage28/docs_extract/index.json"],
        "basis": "Russian by its own text (a multi-language file: Russian, Ukrainian, Kazakh, Uzbek sections); the exact catalog code DW60M5050BB is named in the text; no other model is named.",
        "facts": facts,
    }
    path = ROOT / "product_tool/config/samsung_recorded_documents.v1.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["documents"] = [d for d in data["documents"] if not (d["article"] == entry["article"] and d["href"] == entry["href"])] + [entry]
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("recorded", entry["article"], entry["pages"], "pages;", facts["names_catalog_model"], "ru", facts["russian_by_text"])


if __name__ == "__main__":
    main()
