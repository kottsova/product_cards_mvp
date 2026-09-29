import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, r'A:\work\dev\product_cards_mvp')
from product_tool.census.structural_contracts_v8 import inspect_structure

DBS = [
    'reports/source_census_2026-09-22_stage5_1/source_snapshots.sqlite3',
    'reports/source_census_2026-09-22_stage6/source_snapshots.sqlite3',
    'reports/source_census_2026-09-22_stage6_1/source_snapshots.sqlite3',
    'reports/source_census_2026-09-22_stage7/source_snapshots.sqlite3',
    'reports/source_census_2026-09-22_stage7_1/new_source_snapshots.sqlite3',
]

PROFILES = {
    'samsung_kr': ('www.samsung.com',),
    'samsung_kz': ('samsung.com',),
    'samsung_kz_02d9e6': ('www.samsung.com',),
    'samsung_us': ('www.samsung.com',),
    'lg_kr': ('www.lge.co.kr',),
    'lg_kz': ('lg.com', 'www.lg.com'),
    'playstation_global_candidate': ('playstation.com',),
}

results = {}
for db in DBS:
    if not Path(db).exists():
        continue
    conn = sqlite3.connect(db)
    cur = conn.cursor()
    try:
        cur.execute("SELECT source_id, source_url, content, content_sha256, fetched_at FROM source_snapshots")
    except sqlite3.OperationalError as e:
        print(db, 'ERR', e)
        continue
    for source_id, url, content, sha, fetched_at in cur.fetchall():
        if source_id not in PROFILES:
            continue
        hosts = PROFILES[source_id]
        try:
            struct = inspect_structure(content, url, hosts)
        except Exception as e:
            results.setdefault(source_id, []).append({'db': db, 'url': url, 'error': str(e)})
            continue
        entry = {
            'db': db, 'url': url, 'sha256_matches': sha == struct['content_sha256'],
            'is_product_page': struct['is_product_page'], 'observed': struct['observed'],
            'num_links': len(struct['links']),
            'product_links': [l['url'] for l in struct['links'] if l['kind'] == 'product'][:15],
            'category_links_sample': [l['url'] for l in struct['links'] if l['kind'] == 'category'][:8],
            'content_len': len(content),
            'content_head': content[:200],
        }
        results.setdefault(source_id, []).append(entry)

for sid, entries in results.items():
    print('=====', sid, '(', len(entries), 'snapshots )')
    for e in entries:
        if 'error' in e:
            print('  ERROR', e['url'], e['error']); continue
        print('  URL:', e['url'], '| len=', e['content_len'], '| is_product_page=', e['is_product_page'])
        if e['product_links']:
            print('    product_links:', e['product_links'])
        if e['category_links_sample']:
            print('    category_links:', e['category_links_sample'][:5])

Path(r'A:\work\dev\product_cards_mvp\reports\source_census_2026-09-22_stage8_2\offline_reprocess.json').write_text(
    json.dumps(results, indent=2, ensure_ascii=False), encoding='utf-8')
