"""Stage 10.2 phase 2 -- fetch the Russian-locale equivalent of the two candidate
hardware-setup articles, confirmed present in support.xbox.com's own ru-RU
sitemap (phase 1), not guessed."""
import json

from lib import OUT, RequestLogger, load_budget, make_probe
from product_tool.census.models import EndpointCapability

budget = load_budget()
allowed_hosts = tuple(budget['allowed_hosts'])
probe = make_probe(budget)
logger = RequestLogger()

urls = [
    'https://support.xbox.com/ru-RU/help/hardware-network/console/unbox-xbox-series-xs-console',
    'https://support.xbox.com/ru-RU/help/hardware-network/getting-started-set-up/set-up-new-series-x-s',
]

results = {}
for url in urls:
    result = probe.probe(url, allowed_hosts=allowed_hosts, capability=EndpointCapability.SUPPORT_PAGE, sample_type='manual_candidate_ru')
    entry = logger.record(url, EndpointCapability.SUPPORT_PAGE, result, note='confirmed present in ru-RU sitemap (phase 1), not guessed')
    text = getattr(result, 'diagnostic_text', '') or ''
    safe = url.rsplit('/', 1)[-1]
    (OUT / 'raw' / f'support_ru_{safe}.html.txt').write_text(text, encoding='utf-8', errors='replace')
    results[url] = {
        'access_status': result.access_status.value,
        'http_status': result.http_status,
        'bytes_read': entry['bytes_read'],
        'text_len': len(text),
        'requires_js': '<noscript>' in text and 'enable javascript' in text.lower(),
        'has_preloaded_state_or_readable_body_text': ('__PRELOADED_STATE__' in text) or (len(text) > 5000),
    }

output = {'phase': 'ru_article_fetch', 'results': results, 'request_log': logger.entries}
(OUT / 'phase2_ru_article_fetch.json').write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding='utf-8')
print(json.dumps(output, indent=2, ensure_ascii=False))
