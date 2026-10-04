"""Rerun only explicitly affected frozen Samsung models after a general fix."""
from pathlib import Path
import json, sqlite3, sys, traceback
from product_tool import card_evidence, jobs, samsung_readiness, worker
root = Path(__file__).resolve().parent
path = root / 'post_fix.sqlite3'
requested = set(sys.argv[1:])
known = json.loads((root / 'dataset_frozen.json').read_text(encoding='utf-8-sig'))['models']
assert requested and requested <= {x['article'] for x in known}
results = {x['article']: x for x in json.loads((root / 'post_fix.json').read_text(encoding='utf-8'))}
with sqlite3.connect(path) as db:
    rows = {code: pid for pid, code in db.execute('select id, search_code from products')}
for article in [x['article'] for x in known if x['article'] in requested]:
    pid = rows[article]
    try:
        jid = jobs.enqueue(path, pid, [1, 2, 3, 4, 6])
        processed = worker.run_once(path)
        error = ''
    except Exception:
        processed, error = False, traceback.format_exc()
    history = jobs.list_jobs(path, pid)
    job = history[0] if history else {'status': 'enqueue_error', 'message': error, 'id': ''}
    old = results[article]
    results[article] = {**old, 'processed': processed, 'exception': error,
                        'job_status': job['status'], 'job_message': job['message'],
                        'pages': jobs.get_source_pages(path, pid), 'documents': jobs.get_documents(path, pid),
                        'facts': jobs.get_facts(path, pid), 'photos': jobs.get_photo_candidates(path, pid),
                        'readiness': samsung_readiness.card_readiness(path, pid),
                        'page_evidence': card_evidence.load(path, pid, 'samsung_page'),
                        'document_evidence': card_evidence.load(path, pid, 'samsung_documents'),
                        'dealer_evidence': card_evidence.load(path, pid, 'dealer'),
                        'events': jobs.list_events(path, job['id']) if job['id'] else []}
    (root / 'refined.json').write_text(json.dumps([results[x['article']] for x in known], ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    print(json.dumps({'article': article, 'status': job['status'], 'readiness': results[article]['readiness']['verdict'],
                      'gaps': results[article]['readiness']['blocking_gaps'], 'error': bool(error)}, ensure_ascii=False), flush=True)
