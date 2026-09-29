import json
from pathlib import Path
from collections import Counter
from urllib.parse import urlsplit

OUT = Path(r'A:\work\dev\product_cards_mvp\reports\source_census_2026-09-22_stage8_6')
STAGE85_CARD = json.loads((Path(r'A:\work\dev\product_cards_mvp\reports\source_census_2026-09-22_stage8_5\card.json')).read_text(encoding='utf-8'))

MANUAL_URL = "https://org.downloadcenter.samsung.com/downloadfile/ContentsFile.aspx?CDSite=UNI_KZ_RU&OriginYN=N&ModelType=N&ModelName=MS23K3614AK&CttFileID=7400287&CDCttType=UM&VPath=UM%2F201907%2F20190723164117830%2FMS23K3614AK_BW_DE68-04547Q-00_RU-UK-KK-UZ.pdf"
MANUAL_FINAL_URL = "https://downloadcenter.samsung.com/content/UM/201907/20190723164117830/MS23K3614AK_BW_DE68-04547Q-00_RU-UK-KK-UZ.pdf"

updated_card = json.loads(json.dumps(STAGE85_CARD))  # deep copy via round-trip
updated_card['schema_version'] = 'stage8_6_updated_card.v1'
updated_card['supersedes'] = 'reports/source_census_2026-09-22_stage8_5/card.json (unmodified; this is a new, separate artifact)'
updated_card['fields']['instruction_manual'] = {
    "value": MANUAL_FINAL_URL,
    "status": "confirmed_by_content",
    "url": MANUAL_URL,
    "final_url": MANUAL_FINAL_URL,
    "evidence": (
        "Full 10,572,005-byte file assembled via bounded HTTP Range requests (8 parts, all matching ETag/Last-Modified, size verified "
        "against Content-Range total). Parsed cleanly as an 80-page PDF. Content confirms: (1) it is a user manual ('Руководство "
        "пользователя' on the cover page), (2) the exact catalog model code 'MS23K3614AK_BW' appears 20 times per language section in "
        "an embedded production filename footer (80 occurrences total), stronger than the cover's 'MS23K3614A*' family wildcard alone, "
        "(3) all 4 languages the filename claimed (RU-UK-KK-UZ) are genuinely present as real prose content, confirmed page-by-page."
    ),
    "pages": 80,
    "languages_confirmed_by_content": ["Russian (pages 1-19)", "Ukrainian (pages 20-39)", "Kazakh (pages 40-59)", "Uzbek (pages 60-79)"],
}
updated_card['manual_confirmed_by_content'] = True
updated_card['manual_confirmed_by_content_note'] = "Reversed from Stage 8.5's 'not confirmed' -- the full file was obtained this stage via bounded Range-based assembly and its content was read directly."
updated_card['russian_language_confirmed'] = True
updated_card['russian_language_confirmed_note'] = "Confirmed by content this stage: pages 1-19 are a complete, readable Russian-language manual section, not inferred from the filename."
updated_card['export_readiness'] = {
    "status": "ready_with_minor_gaps",
    "ready_fields": ["brand", "model_name", "manufacturer_model_code", "color", "volume", "power_consumption", "output_power", "official_image", "instruction_manual"],
    "blocking_or_flagged_gaps": [
        "6 physical/control characteristics (weight, dimensions, turntable diameter, control type, auto-program/power-level counts, defrost mode list) still have no confirmed value -- unchanged from Stage 8.5, not addressed this stage (out of this stage's scope, which was the document-verification capability only).",
    ],
    "recommendation": "The instruction-manual gap that previously blocked full confidence is now closed with genuine content evidence. The card can be exported with the 9 confirmed fields; the 6 missing physical characteristics remain an explicitly flagged, non-blocking gap.",
}
json.dump(updated_card, open(OUT / 'updated_card.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)

# ---------------------------------------------------------------------------
# checkpoint.json
# ---------------------------------------------------------------------------
run_state = json.loads((OUT / 'run_state.json').read_text(encoding='utf-8'))
log = []
running_host = Counter()
for i, a in enumerate(run_state['attempts']):
    host = urlsplit(a['url']).hostname
    running_host[host] += 1
    log.append({
        'seq': i + 1, 'url': a['url'], 'kind': a.get('kind'), 'range_requested': a.get('range_requested'),
        'http_status': a.get('http_status'), 'content_range_header': a.get('content_range_header'),
        'bytes_read': a.get('bytes_read'), 'etag': a.get('etag'), 'last_modified': a.get('last_modified'),
        'total_after': i + 1, 'host_after': dict(running_host),
    })

checkpoint = {
    "schema_version": "stage8_6_checkpoint.v1",
    "budget_declared_before_first_request": json.loads((OUT / 'budget_predeclaration.json').read_text(encoding='utf-8')),
    "budget_revision_declared_before_further_requests": json.loads((OUT / 'budget_revision.json').read_text(encoding='utf-8')),
    "budget_actual": {
        "total_requests": len(run_state['attempts']),
        "by_host": dict(Counter(urlsplit(a['url']).hostname for a in run_state['attempts'])),
        "hosts_contacted": sorted({urlsplit(a['url']).hostname for a in run_state['attempts']}),
        "within_revised_plan": len(run_state['attempts']) <= 12,
    },
    "rejected_attempts": run_state.get('rejected_attempts', []),
    "rejected_attempts_note": "Kept separate from executed requests -- empty this stage; every call stayed within whichever budget (original or revised) was in force at the time.",
    "request_log": log,
    "hosts_paused_this_run": run_state['blocked_hosts'],
    "version_consistency_check_result": "All 9 requests (1 from the first, capped attempt + 8 from the successful assembly) returned the IDENTICAL ETag ('0863cfa2a41d51:0') and Last-Modified ('Tue, 23 Jul 2019 07:48:12 GMT') -- confirmed no version drift across parts; no splicing risk.",
    "assembly_attempts": {
        "attempt_1_original_6mb_cap": "reports/source_census_2026-09-22_stage8_6/assembly_result_attempt1_6mb_cap.json -- stopped cleanly at the size-check gate (declared total 10,572,005 bytes > 6,000,000-byte cap), 0 bytes fetched beyond the first probe chunk, status unknown_completeness -- correct, safe behavior.",
        "attempt_2_revised_12mb_cap": "reports/source_census_2026-09-22_stage8_6/assembly_result.json -- succeeded, status complete, 10,572,005/10,572,005 bytes assembled.",
    },
    "counter_persistence": "Continues Stage 8.3-8.5's fix unchanged: total and per-host counts are always recomputed from this stage's own run_state.json.",
    "ordinary_page_load_limit": "Unchanged at 1,500,000 bytes; not used in this stage's requests (all were document Range/probe requests to the PDF host, not HTML page fetches).",
    "new_tooling": "pypdf 6.19.0 (already installed in Stage 8.5, reused here, local gitignored .venv only).",
}
json.dump(checkpoint, open(OUT / 'checkpoint.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
print('wrote updated_card.json, checkpoint.json')
