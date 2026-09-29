"""Apply one verified attended LG capture to an existing row, entirely offline."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import time
from pathlib import Path

from product_tool import jobs
from product_tool.adapters.lg_support import LGSupportAdapter, support_payload_codes
from product_tool.adapters.lg import lg_article_components
from product_tool.fetch_history import record_fetch_attempt, save_source_snapshot
from product_tool.readiness import card_readiness


def _saved_bytes(directory: Path, name: str, expected_sha: str) -> bytes:
    data = gzip.open(directory / name, "rb").read()
    if hashlib.sha256(data).hexdigest() != expected_sha:
        raise ValueError("Captured response hash mismatch")
    return data


class _PdfResponse:
    status_code = 200
    truncated = False

    def __init__(self, url: str, data: bytes):
        self.url, self.text = url, data.decode("latin-1")

    def raise_for_status(self):
        pass


class _OneSavedPdf:
    def __init__(self, url: str, data: bytes):
        self.url, self.data = url, data

    def get(self, url: str, **_):
        if url != self.url:
            raise ValueError("PDF URL differs from captured official link")
        return _PdfResponse(url, self.data)


def apply_capture(database: Path, batch_id: str, product_id: int, directory: Path) -> dict:
    product = jobs.get_product(database, product_id)
    if not product or product["batch_id"] != batch_id or product["brand"].strip().casefold() != "lg":
        raise ValueError("Existing LG row in the named batch is required")
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    pdf_check = json.loads((directory / "pdf_check.json").read_text(encoding="utf-8"))
    if manifest["outcome"] != "captured" or not manifest.get("rendered_dom"):
        raise ValueError("No successful rendered capture")
    url = manifest["url"]
    if url not in {page["url"] for page in jobs.get_source_pages(database, product_id)
                   if page["source_key"] == "lg_kz_support"}:
        raise ValueError("Support URL was not already observed for this row")
    html = gzip.open(directory / manifest["rendered_dom"], "rt", encoding="utf-8").read()
    api_record = next((item for item in manifest["responses"]
                       if item.get("status") == 200 and item.get("method") == "POST"
                       and "/ncms/api/v1/support/proxy/productSupportPage" in item.get("url", "")
                       and item.get("saved")), None)
    if not api_record:
        raise ValueError("Official product support API response missing")
    api_bytes = _saved_bytes(directory, api_record["saved"], api_record["sha256"])
    payload = json.loads(api_bytes)
    components = set(lg_article_components(product["search_code"]))
    if not components.issubset(set(support_payload_codes(payload))):
        raise ValueError("Official support response does not link every catalog component")
    pdf = (directory / "russian_manual.pdf").read_bytes()
    if (hashlib.sha256(pdf).hexdigest() != pdf_check.get("sha256")
            or not pdf.startswith(b"%PDF-") or pdf_check.get("status") != 200
            or pdf_check.get("truncated")):
        raise ValueError("The complete captured PDF has not been verified")
    adapter = LGSupportAdapter(candidate_urls=(url,), candidate_pages={url: html},
                               candidate_payloads={url: payload},
                               documents_http=_OneSavedPdf(pdf_check["url"], pdf))
    deadline = time.monotonic() + 20
    source = adapter.find_source(product["search_code"], deadline=deadline)
    if source.match_level != "full_sku" or source.url != url:
        raise ValueError("Official support identity not established")
    documents, report = adapter.find_documents(source, product["search_code"], deadline=deadline)
    if len(documents) != 1 or report["outcome"] != "verified_russian_instruction":
        raise ValueError("Russian PDF not verified by the adapter")
    # Preserve specifications, photos and descriptions from all prior stages.
    jobs.save_source_document(database, product_id, source,
                              update_description=False, update_attributes=False, update_photos=False)
    attempt = record_fetch_attempt(database, product_id, "lg_kz_support_api", status="success",
                                   requested_url=api_record["url"], final_url=api_record["url"],
                                   http_status=200)
    save_source_snapshot(database, product_id, "lg_kz_support_api", attempt,
                         source_url=api_record["url"], content=api_bytes.decode("utf-8"),
                         content_type="application/json",
                         extracted={"support_url": url, "sales_codes": sorted(components),
                                    "manual_url": documents[0].direct_url,
                                    "manual_title": documents[0].title,
                                    "manual_language": documents[0].language,
                                    "pdf_sha256": pdf_check["sha256"],
                                    "pdf_model_references": report["files"][0]["assessment"]["model_references"],
                                    "evidence_relation": report["files"][0]["evidence_relation"],
                                    "official_source": True})
    jobs.save_documents(database, product_id, source.source_key, documents)
    return {"product_id": product_id, "support_url": url, "match_level": source.match_level,
            "document_url": documents[0].direct_url, "document_title": documents[0].title,
            "document_relation": report["files"][0]["evidence_relation"],
            "pdf_model_references": report["files"][0]["assessment"]["model_references"],
            "readiness": card_readiness(database, product_id)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline replay of an attended LG capture")
    parser.add_argument("database", type=Path)
    parser.add_argument("batch_id")
    parser.add_argument("product_id", type=int)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    print(json.dumps(apply_capture(args.database, args.batch_id, args.product_id, args.directory),
                     ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
