import json
from pathlib import Path

OUT = Path(r'A:\work\dev\product_cards_mvp\reports\source_census_2026-09-22_stage8_6')

offline_review = {
    "schema_version": "stage8_6_offline_review.v1",
    "control_document": "Samsung MS23K3614AK/BW manual PDF (already found in Stage 8.4, first content-checked in Stage 8.5)",
    "no_new_product_search": True,
    "reviewed_stage8_5_bytes_and_method": {
        "how_bytes_were_obtained": "Stage 8.5's fetch_binary(): a single plain GET (no Range header) with a hard read cap of 1,500,000 bytes -- the same number as the ordinary HTML page-load limit, reused as a document cap without a dedicated document-retrieval strategy.",
        "size_check_used": "len(chunks joined as bytes) -- i.e. Stage 8.5 ALREADY counted raw binary bytes, not decoded-text length. The text-length bug this task asks to fix belongs to STAGE 8.4 (which measured len() of a UTF-8-decoded string with errors='replace' as a stand-in for byte count) -- Stage 8.5 had already corrected this specific measurement. This stage keeps that correction and adds what was still missing: a bounded way to get PAST a single-request truncation, and an explicit completeness classification (Stage 8.5 only had a boolean 'truncated' flag with no assembly capability).",
        "result": "bytes_read=1,500,000, truncated=True -- the file is provably larger than 1.5MB; Stage 8.5 correctly stopped there rather than declaring the file complete, and left instruction content/language unconfirmed. No saved bytes exist anywhere (Stage 8.5 explicitly does not persist raw PDF bytes into the repo; they lived only in that stage's own scratch directory and were discarded after the run).",
    },
    "what_this_stage_adds": [
        "A completeness classification with three explicit states: complete / partial / unknown_completeness -- never inferred, always derived from Content-Range/Content-Length compared against actual bytes read.",
        "A bounded HTTP Range-based assembly path, used ONLY if the server actually honors Range (206 + parseable Content-Range) -- verified per part, not assumed.",
        "Version-consistency checks across assembled parts (total size in Content-Range, ETag, Last-Modified) -- if any part disagrees with the first part, assembly is aborted rather than splicing potentially different document versions.",
        "A pre-declared, hard ceiling on total document size (MAX_DOCUMENT_TOTAL_BYTES) -- if the server-declared total exceeds it, no further bytes are fetched for that document at all, regardless of remaining request budget.",
    ],
    "conclusion": "Proceeding to a live check is necessary -- no complete or even reliably partial byte set exists offline for this document. The ordinary page-load cap (1,500,000 bytes) is left untouched and continues to apply to any HTML page fetch; it is not what governs the document-assembly path below.",
}
json.dump(offline_review, open(OUT / 'offline_review.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)

budget_predeclaration = {
    "schema_version": "stage8_6_budget_predeclaration.v1",
    "declared_before_any_request": True,
    "ordinary_page_load_limit_unchanged": {"bytes": 1_500_000, "note": "Left exactly as in every prior stage; governs fetch() for HTML pages only, not used here."},
    "document_assembly_limits": {
        "max_document_total_bytes": 6_000_000,
        "document_chunk_bytes_per_request": 1_500_000,
        "note": "If a document's server-declared total size (via Content-Range or Content-Length) exceeds max_document_total_bytes, no further bytes are fetched for it -- this is a hard stop, not a soft preference.",
    },
    "request_limits": {"max_total_requests": 8, "max_requests_per_host": 6, "max_hosts": 2},
    "pre_declared_allowed_hosts": ["org.downloadcenter.samsung.com", "downloadcenter.samsung.com"],
    "stop_conditions": [
        "403 or 429 response on any host -- that host is paused for the remainder of the run, per ProbePolicy.",
        "A redirect to a host outside the pre-declared allow-list.",
        "Content-Range total size disagrees between two parts of the same assembly (possible different document version) -- assembly aborted.",
        "ETag or Last-Modified disagrees between two parts -- assembly aborted.",
        "Server-declared total size exceeds max_document_total_bytes -- no further fetch for that document.",
        "Range not honored by the server AND Content-Length is missing or exceeds the cap -- no unbounded fallback download is attempted.",
        "Total or per-host request budget exhausted.",
    ],
    "no_chromium_no_search_engines_no_dealers_no_invented_urls": True,
    "target_url": "https://org.downloadcenter.samsung.com/downloadfile/ContentsFile.aspx?CDSite=UNI_KZ_RU&OriginYN=N&ModelType=N&ModelName=MS23K3614AK&CttFileID=7400287&CDCttType=UM&VPath=UM%2F201907%2F20190723164117830%2FMS23K3614AK_BW_DE68-04547Q-00_RU-UK-KK-UZ.pdf",
    "target_url_provenance": "The exact same URL already established in Stage 8.4/8.5 -- not a new discovery, not invented.",
}
json.dump(budget_predeclaration, open(OUT / 'budget_predeclaration.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
print('wrote offline_review.json, budget_predeclaration.json')
