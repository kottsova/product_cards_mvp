"""Stage 66: unchanged baseline/first pass, followed by adapter acceptance.

Run from repository root with python -m reports.playstation_stage66.run_audit MODE.
The frozen dataset is never generated or altered by a run.
"""
import hashlib
import json
import sys
from pathlib import Path
from product_tool import jobs, storage, worker, readiness, discovery_trace, card_evidence

ROOT = Path('reports/playstation_stage66')
BASELINE = dict(article='CFI-2016A', name='PlayStation 5 Slim Disc 1TB CFI-2016A', category='consoles')

def run(mode):
    ROOT.mkdir(exist_ok=True)
    dataset = ROOT / 'dataset_frozen.json'
    digest = hashlib.sha256(dataset.read_bytes()).hexdigest() if dataset.exists() else None
    rows = [BASELINE] if mode.startswith('baseline') else json.loads(dataset.read_text(encoding='utf-8'))['models']
    if mode in {'baseline', 'first_pass'}:
        assert 'playstation_pipeline.run_job' not in Path('product_tool/worker.py').read_text(encoding='utf-8'), 'Requires original Stage 65 worker'
    database = ROOT / (mode + '.sqlite3')
    assert not database.exists(), 'Preserve historical run; use a new mode name'
    jobs.initialize(database)
    with storage._connection(database) as db:
        db.execute('INSERT INTO batches VALUES (?,?,?,?,?)', ('ps66', 'PlayStation Stage 66', 'Products', '{}', storage._now()))
        for number, row in enumerate(rows, 1):
            db.execute('INSERT INTO products (batch_id,row_number,name,brand,search_code,alternate_code,category,needs_confirmation,issues_json,original_values_json) VALUES (?,?,?,?,?,?,?,?,?,?)', ('ps66', number, row['name'], 'PlayStation', row['article'], '', row['category'], 0, '[]', '{}'))
    results = []
    for product in storage.get_batch(database, 'ps66')['products']:
        pid = product['id']; jid = jobs.enqueue(database, pid, [1,2,3,4,6])
        factory=None
        if mode.startswith('release_replay') or mode.startswith('baseline_final') or mode=='release_acceptance':
            from .replay_session import CapturedSession
            from product_tool.adapters.playstation import PlayStationAdapter
            trace=lambda e:discovery_trace.record(database,jid,pid,e)
            factory=lambda:PlayStationAdapter(fetch_log_path=ROOT/'replay_http.json',trace_callback=trace,session=CapturedSession(ROOT))
        worker.run_once(database,playstation_adapter_factory=factory)
        try:
            trace = discovery_trace.for_job(database, jid)
        except (AttributeError, TypeError):
            trace = []
        results.append(dict(input=product, job=jobs.list_jobs(database,pid)[0], sources=jobs.get_source_pages(database,pid), facts=jobs.get_facts(database,pid), resolved=jobs.get_resolved(database,pid), photos=jobs.get_photo_candidates(database,pid), documents=jobs.get_documents(database,pid), readiness=readiness.card_readiness(database,pid), events=jobs.list_events(database,jid), trace=trace, evidence=card_evidence.load(database,pid,'playstation')))
        (ROOT / (mode + '.json')).write_text(json.dumps(dict(mode=mode, dataset_sha256=digest, results=results), ensure_ascii=False, indent=2, default=str), encoding='utf-8')
        print(product['search_code'], results[-1]['job']['status'], len(results[-1]['facts']), results[-1]['readiness']['verdict'], flush=True)
    if digest:
        assert hashlib.sha256(dataset.read_bytes()).hexdigest() == digest

if __name__ == '__main__':
    run(sys.argv[1])
