import json
from pathlib import Path

OUT = Path(r'A:\work\dev\product_cards_mvp\reports\source_census_2026-09-22_stage8_5')

pdf_verification = {
    "schema_version": "stage8_5_pdf_content_verification.v1",
    "url": "https://org.downloadcenter.samsung.com/downloadfile/ContentsFile.aspx?CDSite=UNI_KZ_RU&OriginYN=N&ModelType=N&ModelName=MS23K3614AK&CttFileID=7400287&CDCttType=UM&VPath=UM%2F201907%2F20190723164117830%2FMS23K3614AK_BW_DE68-04547Q-00_RU-UK-KK-UZ.pdf",
    "final_url": "https://downloadcenter.samsung.com/content/UM/201907/20190723164117830/MS23K3614AK_BW_DE68-04547Q-00_RU-UK-KK-UZ.pdf",
    "method": {
        "tooling": "pypdf 6.19.0, installed into the local .venv (gitignored, no tracked project file changed) specifically for this stage's content check.",
        "fetch_path": "fetch_binary() -- a scoped, binary-safe extension of the existing AccessProbe pipeline (same session, same ProbePolicy timeout/max_bytes/user-agent, same redirect-host safety check and 403/429 handling), added because AccessProbe.probe() decodes every response as text (bytes.decode(..., errors='replace')) before returning it, which is a lossy, unrecoverable transform for binary PDF content. No Chromium, no browser automation.",
        "size_limit_respected": "Same 1,500,000-byte cap as every prior stage's ProbePolicy (not raised for this fetch).",
    },
    "fetch_result": {
        "http_status": 200,
        "content_type": "application/pdf",
        "bytes_read": 1_500_000,
        "truncated": True,
        "magic_bytes_confirmed": "%PDF-1.6",
    },
    "important_correction_to_stage_8_4": (
        "Stage 8.4 recorded content_len=1,431,426 (under the 1.5MB cap) via the lossy text-decode path and read this as evidence the FULL "
        "file had likely been captured. That inference was invalid: 1,431,426 was len() of a UTF-8-decoded STRING (with invalid byte "
        "sequences collapsed to single U+FFFD replacement characters), not a count of raw bytes -- string length after lossy decoding does "
        "not equal source byte count for binary content. This stage's binary-safe fetch shows the true behavior: the response hit the "
        "1,500,000-byte cap and was truncated. This correction is noted for the record, not to fault Stage 8.4 (which explicitly flagged "
        "that it had not opened the file), but because it explains why content extraction fails below."
    ),
    "parse_attempt": {
        "library": "pypdf.PdfReader(path, strict=False)",
        "constructor_result": "Succeeded with warnings ('incorrect startxref pointer', 'parsing for Object Streams', 'Object 8629 0 not defined.') -- pypdf's recovery mode rebuilt a partial trailer.",
        "trailer_recovered": "{'/Root': IndirectObject(8646,0,...), '/Info': IndirectObject(8644,0,...), '/Size': 8689}",
        "root_object_access": "Succeeded: {'/MarkInfo','/Metadata','/Names','/Outlines','/Pages','/StructTreeRoot','/Type'} keys visible.",
        "pages_access": "FAILED: PdfReadError 'Invalid object in /Pages' (references object 8629, which is beyond the truncation point and was never downloaded).",
        "info_dictionary_access": "FAILED: AttributeError -- object 8644 (the /Info dictionary, which normally carries Title/Author/document metadata) was also not defined, i.e. it lives beyond the truncated 1.5MB and is unrecoverable from this download.",
        "raw_byte_string_search": "Searched the raw truncated bytes directly for ASCII 'MS23K3614AK', 'MS23K3614', 'Title', '/Lang' -- none found. This is consistent with a normally-structured PDF whose content streams are compressed (FlateDecode); readable text cannot be grepped as plain bytes without decompressing via the (here, broken) object/page tree.",
    },
    "conclusion": {
        "text_extracted": False,
        "model_explicitly_stated_in_content": "not_confirmed",
        "document_language_from_content": "not_confirmed",
        "reason": "The PDF's cross-reference table, page tree, and document info dictionary (all of which normally sit near the end of a PDF file) fall beyond the 1.5MB fetch cap and were never downloaded. This is a genuine, diagnosed technical limitation (not a vague failure) -- the file is demonstrably real (valid PDF magic bytes, correct content-type, a partially-recoverable trailer/root object) but its content cannot be read with the available safe tooling within the existing, unmodified size limit.",
        "official_status": "official PDF candidate; content/language not confirmed",
        "language_not_inferred_from_filename": "Per instructions, the RU-UK-KK-UZ filename suffix is NOT used as a substitute for content-confirmed language. It remains recorded only as first-party linkage/naming metadata (see evidence_separation.json), not as a language finding.",
    },
}
json.dump(pdf_verification, open(OUT / 'pdf_content_verification.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
print('wrote pdf_content_verification.json')
