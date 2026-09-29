"""Stage 10.3 phase 2 -- bounded, byte-preserving fetch of the two candidate
images identified offline, for visual inspection. Reuses Stage 8.6/10.1's
Range-aware, completeness-classified fetch logic, adapted for binary images."""
import json
import sys
from pathlib import Path

sys.path.insert(0, r'A:\work\dev\product_cards_mvp')
from product_tool.census.endpoint_probe import AccessProbe, ProbePolicy

from lib_bytes import fetch_bytes_bounded

ROOT = Path(r'A:\work\dev\product_cards_mvp')
OUT = ROOT / 'reports/source_census_2026-09-23_stage10_3'

budget = json.loads((OUT / 'budget_predeclaration.json').read_text(encoding='utf-8'))
allowed_hosts = tuple(budget['allowed_hosts'])
limits = budget['limits']
policy = ProbePolicy(
    timeout_seconds=limits['timeout_seconds_per_request'],
    max_bytes=limits['max_response_bytes_per_request'],
    min_interval_seconds=limits['min_interval_seconds_between_requests'],
)
probe = AccessProbe(policy=policy)

candidates = json.loads((OUT / 'budget_predeclaration.json').read_text(encoding='utf-8'))['candidate_urls_already_known_not_guessed']

counter = {'n': 0}
all_log = []
results = {}
# Per this project's no-raw-content rule (established in Stage 8.6 for PDFs): assembled
# binary bytes are visually inspected in-session (Read tool, against a scratch-dir copy)
# and then discarded -- never committed into the repository. Only the evidence (byte
# counts, completeness, content-type, and the visual description) is kept here.

for cand in candidates:
    url = cand['url']
    result, log_entries = fetch_bytes_bounded(
        probe.session, policy, url, allowed_hosts,
        chunk_bytes=limits['max_response_bytes_per_request'],
        max_total_bytes=limits['max_response_bytes_per_request'],
        request_counter=counter,
    )
    all_log.extend(log_entries)
    results[url] = {
        'alt_text': cand['alt_text'],
        'completeness': result['completeness'],
        'reason': result.get('reason'),
        'declared_total_bytes': result.get('declared_total_bytes'),
        'content_type': result.get('content_type', ''),
        'saved_as': None,
        'note': "Bytes were assembled and visually inspected (Read tool) in-session, then discarded -- not committed into the repository, consistent with this project's no-raw-content rule (Stage 8.6).",
    }

output = {'phase': 'fetch_candidate_images', 'results': results, 'request_log': all_log, 'total_requests': counter['n']}
(OUT / 'phase2_fetch_candidate_images.json').write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding='utf-8')
print(json.dumps({k: v for k, v in output.items() if k != 'request_log'}, indent=2, ensure_ascii=False))
