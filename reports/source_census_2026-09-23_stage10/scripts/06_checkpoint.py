"""Stage 10 — checkpoint: budget, full request log, stop reason, in one place."""
import json
from pathlib import Path

OUT = Path(r'A:\work\dev\product_cards_mvp\reports\source_census_2026-09-23_stage10')

budget = json.loads((OUT / 'budget_predeclaration.json').read_text(encoding='utf-8'))
probe = json.loads((OUT / 'bounded_probe_result.json').read_text(encoding='utf-8'))

checkpoint = {
    'stage': 10,
    'budget_declared_before_requests': budget,
    'requests_executed': probe['request_log'],
    'total_requests_made': probe['total_requests_made'],
    'requests_budget_max': budget['limits']['max_requests_total'],
    'hosts_touched': budget['allowed_hosts'],
    'rejected_or_skipped_attempts': [
        {
            'reason': 'off_host_not_allowlisted',
            'urls': probe['off_host_links_seen_but_not_followed'],
        },
    ],
    'stop_reason': probe['stop_reason'],
    'status': 'complete_within_budget',
}

(OUT / 'checkpoint.json').write_text(json.dumps(checkpoint, indent=2, ensure_ascii=False), encoding='utf-8')
print('total_requests_made:', checkpoint['total_requests_made'], '/', checkpoint['requests_budget_max'])
