import json
import re
from collections import Counter, defaultdict

p = json.load(open('reports/source_census_2026-09-22_stage8/adapter_profiles.v1.json', encoding='utf-8'))
all_profiles = p['profiles']
targets_done = {'xiaomi_global', 'bosch_home', 'dreame', 'hyperx', 'asus', 'delonghi', 'nintendo'}
profiles = [x for x in all_profiles if x['completeness_status'] == 'product_page_not_found']
fam_counts = Counter(x['source_family'] for x in all_profiles)


def cms_engines(item):
    return sorted({c['engine'] for c in item.get('cms_fingerprint', []) if c.get('status') in ('confirmed', 'probable')})


def classify(item):
    domain = item.get('official_domain', '') or ''
    role = item.get('source_role', '')
    cms = cms_engines(item)
    fam = item['source_family']
    routes = ((item.get('layers', {}).get('discovery', {}) or {}).get('contract') or {}).get('routes') or []
    reasons = []
    if item.get('support_status') == 'observed':
        reasons.append(('support_first', 'A support-page sample already yielded document/structure evidence for this profile; extend from the confirmed support endpoint before retrying the product path.'))
    if role in ('support', 'support_portal') or 'support' in domain or 'support' in (item.get('division') or ''):
        reasons.append(('support_first', 'Source role/domain is support-oriented; the manufacturer product catalog likely lives on a separate consumer domain not yet verified.'))
    if any(e in cms for e in ('shopify', 'woocommerce', 'magento', 'salesforce_commerce_cloud', 'adobe_experience_manager')):
        reasons.append(('sitemap_or_catalog_feed', f'Detected commerce platform ({", ".join(e for e in cms if e in ("shopify","woocommerce","magento","salesforce_commerce_cloud","adobe_experience_manager"))}); these platforms expose standard sitemap.xml / sitemap index or catalog feed routes that were not yet walked to a product URL.'))
    if routes:
        reasons.append(('internal_http_search', f'A bounded internal HTML search form/link was already detected ({routes[0]}) on the sampled page; Stage 5.1 bounded internal search can query it directly instead of crawling categories blind.'))
    if fam_counts.get(fam, 0) > 1:
        reasons.append(('regional_official_domain', f'Source family has {fam_counts[fam]} known official/regional profiles; an alternate market mirror may expose a reachable catalog even if this one did not.'))
    if not reasons:
        reasons.append(('official_category', 'Direct HTTP access succeeded on the homepage but no category/product link was resolved within the bounded sample; a dedicated category-first crawl (not just homepage) is the next reproducible step.'))
    # Priority: support_first > internal_http_search > sitemap_or_catalog_feed > regional_official_domain > official_category
    order = ['support_first', 'internal_http_search', 'sitemap_or_catalog_feed', 'regional_official_domain', 'official_category']
    reasons.sort(key=lambda r: order.index(r[0]) if r[0] in order else 99)
    return reasons[0]


groups = defaultdict(list)
for item in profiles:
    bucket, why = classify(item)
    groups[bucket].append({
        'profile_id': item['profile_id'],
        'source_family': item['source_family'],
        'official_domain': item['official_domain'],
        'unique_products': item['unique_products'],
        'cms_engines': cms_engines(item),
        'source_role': item['source_role'],
        'support_status': item.get('support_status'),
        'reason': why,
    })

summary = {k: len(v) for k, v in groups.items()}
print(json.dumps(summary, indent=2, ensure_ascii=False))

out = {
    'schema_version': 'stage8_2_queue.v1',
    'generated_from': 'reports/source_census_2026-09-22_stage8/adapter_profiles.v1.json (read-only baseline)',
    'scope_note': 'Grouping only; Stage 8.1 does not execute this queue. Each group lists a reproducible next method, not a guarantee of success.',
    'total_profiles': len(profiles),
    'groups': {k: v for k, v in groups.items()},
}
with open('reports/source_census_2026-09-22_stage8_1/stage8_2_queue.json', 'w', encoding='utf-8') as f:
    json.dump(out, f, indent=2, ensure_ascii=False)
print('wrote queue with', len(profiles), 'profiles across', len(groups), 'groups')
