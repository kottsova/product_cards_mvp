"""Explicit offline migration of captured Stage 6/6.1 projections; never opens a browser."""
import json
from .runner_v61 import ROOT,OUTPUT,no_browser
from .runner_v5 import source_specs,write_json
from .runner_v4 import _sample_products
from .catalog import load_catalog_coverage
from .browser_contracts import VERSIONS,BrowserBudget
from .browser_runtime import BrowserRuntime
from .browser_strategy import BrowserAssistedSearchStrategy
from .browser_projection import legacy_projection,sanitize_projection
from .browser_snapshots import BrowserSnapshotStore

def execute():
    destination=OUTPUT/'final_reprocessing.json'
    if destination.exists():return json.loads(destination.read_text(encoding='utf-8'))
    observed=json.loads((OUTPUT/'dry_run.json').read_text(encoding='utf-8'))
    runtime=BrowserRuntime(**observed['runtime']);store=BrowserSnapshotStore(OUTPUT/'source_snapshots.sqlite3')
    static_rows={}
    for stage in ('stage5','stage5_1'):
        static_rows.update({r['source_family']:r for r in json.loads((ROOT/('reports/source_census_2026-09-22_'+stage+'/dry_run.json')).read_text(encoding='utf-8'))['runs']})
    catalog=load_catalog_coverage(ROOT/'data/catalog_2026-09-21_filtered.xlsx');specs={s.source_family:s for s in source_specs()};results=[];checkpoints={}
    for row in observed['runs']:
        family=row['source_family'];spec=specs[family];expected=_sample_products(catalog,spec,limit=1)[0]
        args=dict(source_family=family,source_url=row['source_url'],allowed_hosts=spec.allowed_hosts,expected=expected,static_result=static_rows[family]['result'],official_source_verified=True,browser_assisted=True,render_mode=row['render_mode'])
        strategy=BrowserAssistedSearchStrategy(runtime=runtime,budget=BrowserBudget(),browser_factory=no_browser)
        cp=row['result']['checkpoint'];incompatible=strategy.run(**args,checkpoint=cp)
        assert incompatible.stop_reason=='checkpoint_incompatible'
        refs=[];provenance=[]
        for ref in cp['snapshots']:
            saved=store.load(ref);meta=saved['extracted'];projection=json.loads(saved['content'])
            if family=='bosch_home':
                base=json.loads((ROOT/'reports/source_census_2026-09-22_stage6/dry_run.json').read_text(encoding='utf-8'))
                base_ref=next(r for r in base['runs'] if r['source_family']==family)['result']['checkpoint']['snapshots'][0]
                old_store=object.__new__(BrowserSnapshotStore);old_store.path=ROOT/'reports/source_census_2026-09-22_stage6/source_snapshots.sqlite3'
                original=old_store.load(base_ref)
                projection=legacy_projection(original['content'],original['source_url'],spec.allowed_hosts,original['extracted'].get('visible_indices'))
            else:
                projection=sanitize_projection(projection);projection['projection_version']=VERSIONS['projection_version'];projection['origin']='offline_projection_migration'
            state={'url':saved['source_url'],'requested_url':meta.get('requested_url',saved['source_url']),'projection':projection,'render_mode':row['render_mode'],'versions':{**VERSIONS,'browser_runtime_version':runtime.runtime_version,'browser_version':runtime.browser_version},'counts':meta.get('network_counts',{}),'javascript_errors':meta.get('javascript_errors',0)}
            migrated=store.writer(expected,family)(state,meta['phase'],meta['query'],cp['scope_key']);refs.append(migrated)
            provenance.append({'original_reference':ref,'new_reference':migrated,'migration':'offline_legacy_conversion' if family=='bosch_home' else 'offline_projection_schema_migration','original_projection_version':meta.get('projection_version'),'new_projection_version':VERSIONS['projection_version']})
        rebuilt=strategy.run(**args,checkpoint=cp|{'snapshots':refs},reprocess=True,snapshot_loader=store.load)
        if refs:
            checkpoints[family]=rebuilt.checkpoint
            resume=strategy.run(**args,checkpoint=rebuilt.checkpoint)
            assert resume.stop_reason=='checkpoint_complete'
        else:resume=incompatible
        assert rebuilt.budget_used.http_requests==0
        assert rebuilt.strategy_evidence['browser_usage']['contexts']==0
        results.append({'source_family':family,'old_checkpoint_outcome':incompatible.stop_reason,'reprocessing':rebuilt.to_dict(),'resume_outcome':resume.stop_reason,'migration_provenance':provenance,'observed_live_outcome':row['result']['stop_reason']})
    payload={'versions':VERSIONS,'runs':results,'browser_launches':0,'network_requests':0}
    write_json(OUTPUT/'reprocessed_checkpoint.json',checkpoints);write_json(destination,payload)
    return payload

if __name__=='__main__':execute()
