"""Stage 28 step 5 -- OFFLINE. Keep the evidence, drop the weight: for the dishwasher file the Stage 28 attempt downloaded, store its extracted text (gzip) and a record
(url, sha256, bytes, pages, chars) under docs_extract/, then remove the saved body from the response folder and mark the index entry as pruned (url, status, sha256 and bytes stay).
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
    import pypdf
    extract = STAGE / "docs_extract"
    extract.mkdir(exist_ok=True)
    records = []
    for folder in ("dishwasher",):
        directory = STAGE / folder / "responses"
        entries = [json.loads(line) for line in (directory / "index.jsonl").read_text(encoding="utf-8").splitlines()]
        for entry in entries:
            if "downloadcenter.samsung.com" not in entry["url"] or not entry["saved_as"] or entry.get("pruned"):
                continue
            path = directory / entry["saved_as"]
            with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
                data = handle.read().encode("latin-1", errors="replace")
            record = {"url": entry["url"], "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data), "truncated": entry["truncated"], "kind": "pdf" if data[:5] == b"%PDF-" else "other"}
            if record["kind"] == "pdf" and not entry["truncated"]:
                pages = [(p.extract_text() or "") for p in pypdf.PdfReader(io.BytesIO(data)).pages]
                record.update({"pages": len(pages), "chars": sum(len(p) for p in pages), "text_file": f"{record['sha256'][:12]}.txt.gz"})
                with gzip.open(extract / record["text_file"], "wt", encoding="utf-8") as handle:
                    handle.write("\n\f\n".join(pages))
            records.append(record)
            path.unlink()
            entry["saved_as"], entry["pruned"] = "", "text kept in docs_extract" if record.get("text_file") else "body not kept"
        (directory / "index.jsonl").write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in entries), encoding="utf-8")
    (extract / "index.json").write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"documents pruned={len(records)}; texts kept={sum(1 for r in records if r.get('text_file'))}")


if __name__ == "__main__":
    with offline_only():
        main()
