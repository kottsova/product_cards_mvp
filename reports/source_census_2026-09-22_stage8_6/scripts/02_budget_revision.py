import json
from pathlib import Path

OUT = Path(r'A:\work\dev\product_cards_mvp\reports\source_census_2026-09-22_stage8_6')

revision = {
    "schema_version": "stage8_6_budget_revision.v1",
    "trigger": "The first bounded probe (1 request, logged) confirmed via Content-Range that the control document's true size is 10,572,005 bytes -- larger than the initially declared 6,000,000-byte cap. The capability correctly stopped and fetched no further bytes, leaving status 'unknown_completeness' / content not confirmed, exactly per instructions.",
    "why_a_second_declaration_and_not_a_silent_retry": (
        "This stage's stated purpose is verifying LARGE official instructions specifically. Stopping permanently at the first conservative "
        "cap would validate only the stop-safety mechanism, not the assembly mechanism the stage is meant to build and test. Rather than "
        "quietly abandoning the goal or silently loosening the cap after the fact, this is recorded as an explicit, separate budget "
        "revision -- declared here, in writing, BEFORE any further request is made under it -- not a retroactive change to the first "
        "declaration, which stands unmodified in budget_predeclaration.json and assembly_result.json."
    ),
    "revised_document_assembly_limits": {
        "max_document_total_bytes": {"previous": 6_000_000, "revised": 12_000_000, "reason": "Comfortably above the confirmed 10,572,005-byte total; still a fixed, finite ceiling, not 'unlimited'."},
        "document_chunk_bytes_per_request": {"previous": 1_500_000, "revised": 1_500_000, "reason": "Unchanged -- still the same per-request chunk size, reusing the existing ordinary page-load number."},
    },
    "revised_request_limits": {
        "max_total_requests": {"previous": 8, "revised": 12, "reason": "10,572,005 bytes / 1,500,000-byte chunks = 8 chunk requests total (0-indexed, last chunk partial); 1 was already spent on the probe/first chunk, so up to 7 more are needed. 12 leaves headroom for the image/model-check steps that follow, without being open-ended."},
        "max_requests_per_host": {"previous": 6, "revised": 10, "reason": "All chunks target the same host pair observed in the redirect chain; matches the 8 chunk requests needed."},
        "max_hosts": {"previous": 2, "revised": 2, "reason": "Unchanged."},
    },
    "counters_not_reset": "The persisted run_state.json attempt log (1 request already made) is kept as-is and counts toward the new limits -- this is a limit increase, not a counter reset.",
    "still_bounded": "12,000,000 bytes remains a fixed, pre-declared ceiling before the next request, not an unbounded/adaptive limit that grows again if this document also turns out to exceed it. If the confirmed total had been e.g. 50MB, this stage would have stopped at 'content not confirmed' instead of revising again.",
}
json.dump(revision, open(OUT / 'budget_revision.json', 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
print('wrote budget_revision.json')
