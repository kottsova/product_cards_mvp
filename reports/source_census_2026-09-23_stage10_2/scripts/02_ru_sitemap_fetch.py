"""Stage 10.2 phase 1 -- fetch support.xbox.com's ru-RU sitemap, already declared
in the sitemap index Stage 10.1 saved (not guessed), to check for a Russian
equivalent of the two candidate Series X|S hardware-setup articles."""
import json
import re

from lib import OUT, RequestLogger, load_budget, make_probe
from product_tool.census.models import EndpointCapability

budget = load_budget()
allowed_hosts = tuple(budget['allowed_hosts'])
probe = make_probe(budget)
logger = RequestLogger()

url = 'https://support.xbox.com/ru-RU/sitemap.xml'
result = probe.probe(url, allowed_hosts=allowed_hosts, capability=EndpointCapability.SITEMAP, sample_type='sitemap')
entry = logger.record(url, EndpointCapability.SITEMAP, result, note='URL taken verbatim from Stage 10.1\'s already-saved sitemap index, not guessed')

text = getattr(result, 'diagnostic_text', '') or ''
(OUT / 'raw' / 'support_xbox_com_ru_ru_sitemap.xml.txt').write_text(text, encoding='utf-8', errors='replace')

locs = re.findall(r'<loc>([^<]+)</loc>', text)
en_slugs = ['unbox-xbox-series-xs-console', 'set-up-new-series-x-s']
matches = {slug: [u for u in locs if slug in u] for slug in en_slugs}
# Also look for any series-s/series-x hardware-console article under this locale, in case the slug itself was translated
series_related = [u for u in locs if re.search(r'series-x|series-s|xbox-series', u, re.I)]

output = {
    'phase': 'ru_sitemap_fetch',
    'url': url,
    'access_status': result.access_status.value,
    'http_status': result.http_status,
    'bytes_read': entry['bytes_read'],
    'url_count': len(locs),
    'same_slug_matches': matches,
    'other_series_related_urls': series_related[:30],
    'request_log': logger.entries,
}
(OUT / 'phase1_ru_sitemap_fetch.json').write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding='utf-8')
print(json.dumps({k: v for k, v in output.items() if k != 'request_log'}, indent=2, ensure_ascii=False))
