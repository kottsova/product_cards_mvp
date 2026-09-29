"""Offline Stage 48 replay of the seven existing LG rows from saved HTML."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from product_tool import jobs, storage
from product_tool.adapters.lg import extract_lg_attributes, extract_lg_ru_attributes
from product_tool.fetch_history import latest_source_snapshot
from product_tool.normalization import normalize_facts
from product_tool.readiness import card_readiness
from bs4 import BeautifulSoup

IDS=(7,8,9,10,11,12,14)
BATCH='ae3d2cb381744ba8a811e54231233254'

def process(path: Path, *, add_jobs: bool) -> list[dict]:
    jobs.initialize(path)
    report=[]
    for pid in IDS:
        product=jobs.get_product(path,pid)
        assert product and product['batch_id']==BATCH and product['brand'].strip().casefold()=='lg'
        for source, extractor in (('lg_kz',extract_lg_attributes),('lg_ru',extract_lg_ru_attributes)):
            page=next((p for p in jobs.get_source_pages(path,pid) if p['source_key']==source),None)
            snap=latest_source_snapshot(path,pid,source)
            if not page or not snap or not snap['content'] or page['url']!=snap['source_url']:
                continue
            assert hashlib.sha256(snap['content'].encode('utf8')).hexdigest()==snap['content_sha256']
            facts=normalize_facts(extractor(BeautifulSoup(snap['content'],'html.parser')))
            with storage._connection(path) as c:
                c.execute('DELETE FROM extracted_attribute_facts WHERE product_id=? AND source_key=?',(pid,source))
                c.executemany('INSERT INTO extracted_attribute_facts (product_id,source_page_id,source_key,site_name,raw_name,raw_value,section,normalized_name,normalized_value,unit) VALUES (?,?,?,?,?,?,?,?,?,?)',[(pid,page['id'],source,page['site_name'],f.raw_name,f.raw_value,f.section,f.normalized_name,f.normalized_value,f.unit) for f in facts])
        jobs.resolve_product(path,pid)
        rows=jobs.get_resolved(path,pid)
        conflicts=sum(bool(r['conflict']) for r in rows)
        confirmed=sum(bool(r['full_sku_confirmed']) and not bool(r['conflict']) for r in rows)
        pages=jobs.get_source_pages(path,pid)
        exact=any(p['source_key'] in ('lg_kz','lg_ru') and p['match_level']=='full_sku' and not p['error'] for p in pages)
        supplier=any(p['source_key']=='sulpak' and p['match_level']=='full_sku' for p in pages)
        status='needs_review' if conflicts or not (exact or supplier) else 'done'
        if pages and all(p['error'] for p in pages): status='error'
        card=card_readiness(path,pid)
        if add_jobs:
            prior=jobs.list_jobs(path,pid)[0]
            now=storage._now()
            with storage._connection(path) as c:
                c.execute('INSERT INTO search_jobs (id,product_id,stages_json,status,current_stage,message,created_at,updated_at,started_at,finished_at) VALUES (?,?,?,?,?,?,?,?,?,?)',(f'stage48-offline-{pid}',pid,'[3]',status,3,f'Offline Stage 48 replay from saved LG product HTML; confirmed specs={confirmed}, conflicts={conflicts}; card={card["verdict"]}.',now,now,now,now))
                c.execute('INSERT INTO job_events (job_id,stage,level,message,created_at) VALUES (?,?,?,?,?)',(f'stage48-offline-{pid}',3,'info' if status=='done' else 'warning',f'Offline re-extraction and resolution from saved LG snapshots; no source request; previous job {prior["id"]}.',now))
        report.append({'id':pid,'article':product['search_code'],'conflicts':conflicts,'confirmed_specs':confirmed,'status':status,'verdict':card['verdict'],'conflict_names':[r['normalized_name'] for r in rows if r['conflict']]})
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('database',type=Path)
    parser.add_argument('--add-jobs',action='store_true')
    args=parser.parse_args()
    print(json.dumps(process(args.database,add_jobs=args.add_jobs),ensure_ascii=True,indent=2))

