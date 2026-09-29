"""Stage 5.1: immutable baseline comparison and one opt-in bounded refresh."""
import argparse
from dataclasses import asdict
from pathlib import Path
import hashlib
import json
import sqlite3
from contextlib import closing
from .catalog import load_catalog_coverage
from .runner_v4 import _sample_products
from .runner_v5 import source_specs, configured_routes, write_json
from .internal_search_strategy import InternalSearchStrategy, CHECKPOINT_VERSIONS
from .search_snapshots import SearchSnapshotStore
from .search_routes import now
from .sitemap_strategy import DiscoveryBudget

ROOT=Path(__file__).resolve().parents[2]
OUTPUT=ROOT/'reports/source_census_2026-09-22_stage5_1'
BASELINE=ROOT/'reports/source_census_2026-09-22_stage5'


class NoNetwork:
    def probe(self,*args,**kwargs):raise AssertionError('Offline processing attempted a network call')


def inventory():
    items=[]
    for db in (ROOT/'data').rglob('*.sqlite3'):
        with closing(sqlite3.connect(db.resolve().as_uri()+'?mode=ro',uri=True)) as c:
            has_table=bool(c.execute("SELECT 1 FROM sqlite_master WHERE name='source_snapshots'").fetchone())
            count=c.execute('SELECT count(*) FROM source_snapshots').fetchone()[0] if has_table else 0
            items.append({'database':str(db.relative_to(ROOT)),'source_snapshot_table':has_table,'snapshot_count':count})
    return items


def signature(result):
    return [(c.url,c.ranking_score,c.identity_verification) for c in result.candidates]


def execute(*,refresh_missing=False):
    OUTPUT.mkdir(exist_ok=True)
    baseline=json.loads((BASELINE/'dry_run.json').read_text(encoding='utf-8'))
    old_cp=json.loads((BASELINE/'checkpoint.json').read_text(encoding='utf-8'))['runs']
    cp_path=OUTPUT/'checkpoint.json'
    current=json.loads(cp_path.read_text(encoding='utf-8')) if cp_path.exists() else {'runs':{}}
    markers_path=OUTPUT/'refresh_attempts.json'
    markers=json.loads(markers_path.read_text(encoding='utf-8')) if markers_path.exists() else {}
    existing_inventory=inventory();write_json(OUTPUT/'snapshot_inventory.json',{'checked_at':now(),'databases':existing_inventory,'stage5_has_snapshot_references':any(c.get('snapshots') for c in old_cp.values())})
    store=SearchSnapshotStore(OUTPUT/'source_snapshots.sqlite3')
    census=load_catalog_coverage(ROOT/'data/catalog_2026-09-21_filtered.xlsx')
    budget=DiscoveryBudget(max_http_requests=10,max_product_candidates=20,max_product_pages=3,min_interval_seconds=1,deadline_seconds=50)
    partial_path=OUTPUT/'partial_runs.json'
    recorded=json.loads(partial_path.read_text(encoding='utf-8'))['runs'] if partial_path.exists() else []
    results=[]
    for spec in source_specs():
        if spec.source_family not in {'lg_kz','hyperx'}:continue
        expected=_sample_products(census,spec,limit=1)[0]
        assert expected.seller_sku=={'lg_kz':'27ART10AKPL','hyperx':'4P5D4AA'}[spec.source_family]
        key=spec.source_family+':'+expected.seller_sku
        args=dict(source_family=spec.source_family,source_url=spec.source_url,allowed_hosts=spec.allowed_hosts,expected=expected,configured_endpoints=configured_routes(spec),category_hints=(expected.category_raw,))
        offline=InternalSearchStrategy(budget=budget,probe=NoNetwork())
        incompatible=offline.run(**args,checkpoint=old_cp[key])
        previous=current['runs'].get(key,old_cp[key])
        replay=offline.run(**args,checkpoint=previous,reprocess=True,snapshot_loader=store.load)
        initial_status=replay.stop_reason
        mode='snapshot_reprocessing'
        def save(cp):
            current['runs'][key]=cp;write_json(cp_path,current)
        if replay.stop_reason=='snapshot_missing' and refresh_missing:
            if key in markers and markers[key].get('status') != 'setup_failed_before_network':raise RuntimeError('Controlled refresh already attempted for '+key)
            markers[key]={'started_at':now(),'reason':'snapshot_missing','budget':asdict(budget)};write_json(markers_path,markers)
            result=InternalSearchStrategy(budget=budget).run(**args,checkpoint=old_cp[key],refresh=True,snapshot_writer=store.writer(expected,spec.source_family),checkpoint_callback=save)
            mode='explicit_bounded_network_refresh'
        else:
            result=replay;save(result.checkpoint)
        resume=offline.run(**args,checkpoint=result.checkpoint)
        rebuilt=offline.run(**args,checkpoint=result.checkpoint,reprocess=True,snapshot_loader=store.load)
        old=next(r for r in baseline['runs'] if r['source_family']==spec.source_family)['result']
        old_urls={c['url'] for c in old['candidates']};new_urls={c.url for c in result.candidates}
        prior_row=next((x for x in recorded if x['source_family']==spec.source_family),{})
        refresh_http=result.budget_used.http_requests if mode=='explicit_bounded_network_refresh' else prior_row.get('refresh_http_requests',prior_row.get('result',{}).get('budget_used',{}).get('http_requests',0))
        row={'baseline_snapshot_status':'snapshot_missing' if not old_cp[key].get('snapshots') else 'available','refresh_http_requests':refresh_http,'source_family':spec.source_family,'catalog_identity':expected.to_dict(),'initial_snapshot_status':initial_status,'processing_method':mode,'old_checkpoint_outcome':incompatible.stop_reason,'result':result.to_dict(),'baseline_candidates':old['candidates'],'removed_baseline_urls':sorted(old_urls-new_urls),'navigation_service_excluded_in_responses':sum(a['navigation_service_excluded'] for a in result.checkpoint.get('result_audits',[])),'compatible_resume':{'outcome':resume.stop_reason,'new_http_requests':resume.budget_used.http_requests-result.budget_used.http_requests},'snapshot_reprocessing':{'outcome':rebuilt.stop_reason,'http_requests':rebuilt.budget_used.http_requests,'derived_candidates_equal':signature(result)==signature(rebuilt),'result':rebuilt.to_dict()}}
        results.append(row);write_json(OUTPUT/'partial_runs.json',{'runs':results})
        print(f"{spec.source_family}: {len(old['candidates'])} -> {len(result.candidates)} candidates; {result.stop_reason}; HTTP={result.budget_used.http_requests}; offline={rebuilt.stop_reason}",flush=True)
    before=json.loads((OUTPUT/'protected_hashes_before.json').read_text(encoding='utf-8'))
    after={path:hashlib.sha256((ROOT/path).read_bytes()).hexdigest() for path in before}
    write_json(OUTPUT/'protected_hashes_after.json',after)
    assert before==after,'Baseline or production files changed'
    payload={'generated_at':now(),'versions':CHECKPOINT_VERSIONS,'budget':asdict(budget),'runs':results,'protected_files_unchanged':True,'all_brand_census_complete':False}
    write_json(OUTPUT/'dry_run.json',payload)
    return payload


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--refresh-missing',action='store_true')
    execute(refresh_missing=parser.parse_args().refresh_missing)
