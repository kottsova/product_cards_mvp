"""Explicit Stage 6 research command, limited to three catalog products."""
from pathlib import Path
from dataclasses import asdict
import hashlib
import json
from .browser_runtime import discover_runtime
from .browser_contracts import BrowserBudget,eligibility
from .browser_strategy import BrowserAssistedSearchStrategy
from .browser_snapshots import BrowserSnapshotStore
from .runner_v5 import source_specs,write_json
from .runner_v4 import _sample_products
from .catalog import load_catalog_coverage
from .search_routes import now

ROOT=Path(__file__).resolve().parents[2]
OUTPUT=ROOT/'reports/source_census_2026-09-22_stage6'

class NeverBrowser:
    def __call__(self,*args):raise AssertionError('Replay attempted browser launch')


def execute():
    OUTPUT.mkdir(exist_ok=True)
    runtime=discover_runtime();write_json(OUTPUT/'runtime.json',runtime.to_dict())
    budget=BrowserBudget()
    baseline5=json.loads((ROOT/'reports/source_census_2026-09-22_stage5/dry_run.json').read_text(encoding='utf-8'))
    baseline51=json.loads((ROOT/'reports/source_census_2026-09-22_stage5_1/dry_run.json').read_text(encoding='utf-8'))
    rows={r['source_family']:r for r in baseline5['runs']};rows.update({r['source_family']:r for r in baseline51['runs']})
    catalog=load_catalog_coverage(ROOT/'data/catalog_2026-09-21_filtered.xlsx')
    cp_path=OUTPUT/'checkpoint.json';checkpoints=json.loads(cp_path.read_text(encoding='utf-8')) if cp_path.exists() else {'runs':{}}
    marker_path=OUTPUT/'browser_attempts.json';markers=json.loads(marker_path.read_text(encoding='utf-8')) if marker_path.exists() else {}
    store=BrowserSnapshotStore(OUTPUT/'source_snapshots.sqlite3');results=[]
    for spec in source_specs():
        if spec.source_family not in {'lg_kz','bosch_home','dreame'}:continue
        identity=_sample_products(catalog,spec,limit=1)[0]
        assert identity.seller_sku=={'lg_kz':'27ART10AKPL','bosch_home':'SBV45FX01R','dreame':'HHR12A'}[spec.source_family]
        static=rows[spec.source_family]['result'];url=spec.source_url
        if spec.source_family=='dreame':url=static['checkpoint']['routes'][0]['action_url']
        args={'source_family':spec.source_family,'source_url':url,'allowed_hosts':spec.allowed_hosts,'expected':identity,'static_result':static,'official_source_verified':True,'browser_assisted':True}
        key=spec.source_family+':'+identity.seller_sku
        strategy=BrowserAssistedSearchStrategy(runtime=runtime,budget=budget)
        def save(cp):checkpoints['runs'][key]=cp;write_json(cp_path,checkpoints)
        if key in markers and key not in checkpoints['runs']:raise RuntimeError('Incomplete research attempt requires manual review: '+key)
        if key not in checkpoints['runs']:
            markers[key]={'started_at':now(),'eligibility':eligibility(static,True),'runtime_available':runtime.available};write_json(marker_path,markers)
        result=strategy.run(**args,checkpoint=checkpoints['runs'].get(key),snapshot_writer=store.writer(identity,spec.source_family),checkpoint_callback=save)
        replay_strategy=BrowserAssistedSearchStrategy(runtime=runtime,budget=budget,browser_factory=NeverBrowser())
        resume=replay_strategy.run(**args,checkpoint=result.checkpoint)
        rebuilt=replay_strategy.run(**args,checkpoint=result.checkpoint,reprocess=True,snapshot_loader=store.load)
        row={'source_family':spec.source_family,'identity':identity.to_dict(),'source_url':url,'static_outcome':static['checkpoint']['stop_reason'],'eligibility':eligibility(static,True),'result':result.to_dict(),'resume':{'outcome':resume.stop_reason,'browser_usage':resume.strategy_evidence['browser_usage']},'snapshot_reprocessing':{'outcome':rebuilt.stop_reason,'browser_usage':rebuilt.strategy_evidence['browser_usage'],'candidate_identities_equal':[(c.url,c.identity_verification) for c in result.candidates]==[(c.url,c.identity_verification) for c in rebuilt.candidates]}}
        results.append(row);write_json(OUTPUT/'partial_runs.json',{'runs':results})
        print(spec.source_family,result.stop_reason,result.strategy_evidence['browser_usage'],flush=True)
    before=json.loads((OUTPUT/'protected_hashes_before.json').read_text(encoding='utf-8'));after={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in before}
    write_json(OUTPUT/'protected_hashes_after.json',after)
    assert before==after,'Protected baseline changed'
    payload={'generated_at':now(),'runtime':runtime.to_dict(),'budget':asdict(budget),'runs':results,'protected_files_unchanged':True}
    write_json(OUTPUT/'dry_run.json',payload)
    return payload

if __name__=='__main__':execute()
