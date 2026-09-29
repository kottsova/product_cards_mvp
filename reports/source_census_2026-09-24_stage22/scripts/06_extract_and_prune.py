"""Stage 22 step 6 -- OFFLINE. Keep the evidence, drop the weight.

The live pilot saved every response, including ~30 PDFs (176 MB gz). For each document file it downloaded this script
  1. extracts the text once and stores it gzipped next to a small record (docs_extract/<sha8>.txt.gz + docs_extract/index.json: url, sha256, bytes, pages, chars),
     so the language / model claims of the report can be audited without the PDF;
  2. removes the saved body from pilot2/responses and marks the index entry {"pruned": "text kept in docs_extract"} (url, status, sha256 and bytes stay).
The offline replay (05_run_pilot2.py --replay) was run BEFORE this pruning, on the full bodies; after it a document row cannot be re-run offline without
downloading the files again (their sha256 is in the index).

Output: pilot2/docs_extract/*, pilot2/responses/index.jsonl (rewritten)
"""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import logging
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
STAGE = HERE.parent
sys.path.insert(0, str(ROOT))

from product_tool.offline_guard import offline_only  # noqa: E402

logging.disable(logging.CRITICAL)


def main() -> None:
    directory = STAGE / "pilot2/responses"
    extract = STAGE / "pilot2/docs_extract"
    extract.mkdir(parents=True, exist_ok=True)
    import pypdf
    entries = [json.loads(line) for line in (directory / "index.jsonl").read_text(encoding="utf-8").splitlines()]
    records, freed = [], 0
    for entry in entries:
        if "lge.com" not in entry["url"] or not entry["saved_as"] or entry.get("pruned"):
            continue
        path = directory / entry["saved_as"]
        with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
            data = handle.read().encode("latin-1", errors="replace")
        record = {"url": entry["url"], "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data), "kind": "pdf" if data[:5] == b"%PDF-" else "zip" if data[:2] == b"PK" else "other", "truncated": entry["truncated"]}
        if record["kind"] == "pdf" and not entry["truncated"]:
            try:
                pages = [(p.extract_text() or "") for p in pypdf.PdfReader(io.BytesIO(data)).pages]
                record.update({"pages": len(pages), "chars": sum(len(p) for p in pages), "text_file": f"{record['sha256'][:12]}.txt.gz"})
                with gzip.open(extract / record["text_file"], "wt", encoding="utf-8") as handle:
                    handle.write("\n\f\n".join(pages))
            except Exception as exc:  # noqa: BLE001
                record["parse_error"] = str(exc)[:120]
        records.append(record)
        freed += path.stat().st_size
        path.unlink()
        entry["saved_as"] = ""
        entry["pruned"] = "text kept in docs_extract" if record.get("text_file") else "body not kept (not a complete PDF)"
    (directory / "index.jsonl").write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in entries), encoding="utf-8")
    (extract / "index.json").write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"files pruned={len(records)} freed={freed / 1e6:.0f} MB; texts kept={sum(1 for r in records if r.get('text_file'))}")


if __name__ == "__main__":
    with offline_only():
        main()
