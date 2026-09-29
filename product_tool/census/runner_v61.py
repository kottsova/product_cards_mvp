"""Stage 6.1: two authorized live sources; Bosch is always offline."""
from pathlib import Path
from dataclasses import asdict
import hashlib
import json
from .browser_runtime import discover_runtime
from .browser_contracts import BrowserBudget,VERSIONS
from .browser_strategy import BrowserAssistedSearchStrategy
from .browser_snapshots import BrowserSnapshotStore
from .browser_projection import legacy_projection
from .runner_v5 import source_specs,write_json
from .runner_v4 import _sample_products
from .catalog import load_catalog_coverage
from .search_routes import now

ROOT=Path(__file__).resolve().parents[2]
OUTPUT=ROOT/'reports/source_census_2026-09-22_stage6_1'

def no_browser(*args):raise AssertionError('Offline processing attempted a browser launch')

def execute():
    OUTPUT.mkdir(exist_ok=True)
    if (OUTPUT/'dry_run.json').exists():
        return json.loads((OUTPUT/'dry_run.json').read_text(encoding='utf-8'))
    runtime=discover_runtime();write_json(OUTPUT/'runtime.json',runtime.to_dict());budget=BrowserBudget()
    rows={}
    for stage in ('stage5','stage5_1'):
        rows.update({r['source_family']:r for r in json.loads((ROOT/('reports/source_census_2026-09-22_'+stage+'/dry_run.json')).read_text(encoding='utf-8'))['runs']})
    catalog=load_catalog_coverage(ROOT/'data/catalog_2026-09-21_filtered.xlsx')
    store=BrowserSnapshotStore(OUTPUT/'source_snapshots.sqlite3')
    cp_path=OUTPUT/'checkpoint.json';checkpoints=json.loads(cp_path.read_text(encoding='utf-8')) if cp_path.exists() else {'runs':{}}
    markers_path=OUTPUT/'browser_attempts.json';markers=json.loads(markers_path.read_text(encoding='utf-8')) if markers_path.exists() else {}
    results=[]
    for spec in source_specs():
        family=spec.source_family
        if family not in {'lg_kz','dreame','bosch_home'}:continue
        expected=_sample_products(catalog,spec,limit=1)[0]
        assert expected.seller_sku=={'lg_kz':'27ART10AKPL','dreame':'HHR12A','bosch_home':'SBV45FX01R'}[family]
        static=rows[family]['result'];url=spec.source_url
        if family=='dreame':url=static['checkpoint']['routes'][0]['action_url']
        mode='render_existing_search_result' if family=='lg_kz' else 'interactive_search_ui'
        args=dict(source_family=family,source_url=url,allowed_hosts=spec.allowed_hosts,expected=expected,static_result=static,official_source_verified=True,browser_assisted=True,render_mode=mode)
        key=family+':'+expected.seller_sku
        def save(cp):checkpoints['runs'][key]=cp;write_json(cp_path,checkpoints)
        strategy=BrowserAssistedSearchStrategy(runtime=runtime,budget=budget)
        if family=='bosch_home':
            baseline=json.loads((ROOT/'reports/source_census_2026-09-22_stage6/dry_run.json').read_text(encoding='utf-8'))
            old=next(r['result']['checkpoint'] for r in baseline['runs'] if r['source_family']==family)
            # Never initialize or migrate the immutable baseline database.
            old_store=object.__new__(BrowserSnapshotStore);old_store.path=ROOT/'reports/source_census_2026-09-22_stage6/source_snapshots.sqlite3'
            seed=strategy.run(**(args|{'browser_assisted':False})).checkpoint
            migrated=[];provenance=[]
            for ref in old['snapshots']:
                snapshot=old_store.load(ref);meta=snapshot['extracted']
                projection=legacy_projection(snapshot['content'],snapshot['source_url'],spec.allowed_hosts,meta.get('visible_indices'))
                state={'url':snapshot['source_url'],'requested_url':url,'projection':projection,'render_mode':mode,'versions':{**VERSIONS,'browser_runtime_version':runtime.runtime_version,'browser_version':runtime.browser_version},'counts':{},'javascript_errors':meta.get('javascript_errors',0)}
                migrated.append(store.writer(expected,family)(state,meta['phase'],meta['query'],seed['scope_key']))
                provenance.append({'baseline_reference':ref,'baseline_content_bytes':len(snapshot['content'].encode()),'migration':'offline_legacy_conversion','projection_bytes':len(json.dumps(projection).encode())})
            prior=seed|{'snapshots':migrated}
            result=BrowserAssistedSearchStrategy(runtime=runtime,budget=budget,browser_factory=no_browser).run(**args,checkpoint=prior,reprocess=True,snapshot_loader=store.load,checkpoint_callback=save)
            write_json(OUTPUT/'bosch_offline_provenance.json',provenance)
        else:
            if key in markers:raise RuntimeError('Research already attempted; do not automatically repeat: '+key)
            markers[key]={'started_at':now(),'render_mode':mode};write_json(markers_path,markers)
            result=strategy.run(**args,snapshot_writer=store.writer(expected,family),checkpoint_callback=save)
        offline=BrowserAssistedSearchStrategy(runtime=runtime,budget=budget,browser_factory=no_browser)
        replay=offline.run(**args,checkpoint=result.checkpoint,reprocess=True,snapshot_loader=store.load)
        resume=offline.run(**args,checkpoint=result.checkpoint)
        comparable=lambda r:[(c.url,c.identity_verification) for c in r.candidates]
        row={'source_family':family,'identity':expected.to_dict(),'render_mode':mode,'live':family!='bosch_home','source_url':url,'result':result.to_dict(),'snapshot_reprocessing':{'outcome':replay.stop_reason,'browser_usage':replay.strategy_evidence['browser_usage'],'candidate_identities_equal':comparable(result)==comparable(replay)},'resume':{'outcome':resume.stop_reason,'browser_usage':resume.strategy_evidence['browser_usage']}}
        results.append(row);write_json(OUTPUT/'partial_runs.json',{'runs':results})
        print(family,result.stop_reason,result.strategy_evidence['browser_usage'],flush=True)
    before=json.loads((OUTPUT/'protected_hashes_before.json').read_text(encoding='utf-8'))
    after={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in before}
    write_json(OUTPUT/'protected_hashes_after.json',after)
    assert before==after,'Protected baseline changed'
    decision='retain_as_bounded_fallback' if any(r['result']['candidates'] and r['snapshot_reprocessing']['candidate_identities_equal'] and r['snapshot_reprocessing']['outcome']!='snapshot_missing' for r in results) else 'manual_review_only'
    payload={'generated_at':now(),'runtime':runtime.to_dict(),'budget':asdict(budget),'versions':VERSIONS,'runs':results,'protected_files_unchanged':True,'decision':decision,'production_ready':False}
    write_json(OUTPUT/'dry_run.json',payload)
    return payload

if __name__=='__main__':execute()
