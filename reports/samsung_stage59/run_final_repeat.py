"""Final production repeat on all affected frozen Samsung rows and evidence stability audit."""
from __future__ import annotations
from pathlib import Path
import json, sqlite3, traceback, sys
from product_tool import card_evidence, jobs, samsung_readiness, worker
root = Path(__file__).resolve().parent
path = root / 'post_fix.sqlite3'
items = json.loads((root / 'dataset_frozen.json').read_text(encoding='utf-8-sig'))['models']
with sqlite3.connect(path) as db:
    ids = {code: pid for pid, code in db.execute('select id, search_code from products')}

def snapshot(pid):
    pages = jobs.get_source_pages(path, pid)
    docs = jobs.get_documents(path, pid)
    facts = jobs.get_facts(path, pid)
    photos = jobs.get_photo_candidates(path, pid)
    return {'pages': pages, 'documents': docs, 'facts': facts, 'photos': photos,
            'readiness': samsung_readiness.card_readiness(path, pid)}

targets = set(sys.argv[1:])
prior = json.loads((root / "final_pass.json").read_text(encoding="utf-8")) if targets and (root / "final_pass.json").exists() else []
results = {row["article"]: row for row in prior}
for item in items:
    if targets and item["article"] not in targets:
        continue
    article, pid = item['article'], ids[item['article']]
    before = snapshot(pid)
    try:
        jid = jobs.enqueue(path, pid, [1, 2, 3, 4, 6])
        processed = worker.run_once(path)
        error = ''
    except Exception:
        processed, error = False, traceback.format_exc()
    after = snapshot(pid)
    history = jobs.list_jobs(path, pid)
    job = history[0] if history else {'status': 'enqueue_error', 'message': error, 'id': ''}
    prev_page_urls = {p['url'] for p in before['pages'] if p['source_key'] == 'samsung' and p['url']}
    next_page_urls = {p['url'] for p in after['pages'] if p['source_key'] == 'samsung' and p['url']}
    prev_docs = {d['direct_url'] for d in before['documents'] if d['source_key'] == 'samsung'}
    next_docs = {d['direct_url'] for d in after['documents'] if d['source_key'] == 'samsung'}
    prev_photos = {p['asset_key'] for p in before['photos'] if p['source_key'] == 'samsung' and p['selected']}
    next_photos = {p['asset_key'] for p in after['photos'] if p['source_key'] == 'samsung' and p['selected']}
    repeat = {'page_retained': prev_page_urls <= next_page_urls, 'pdf_retained': prev_docs <= next_docs,
              'selected_photos_retained': prev_photos <= next_photos,
              'document_duplicates': len([d for d in after['documents'] if d['source_key'] == 'samsung']) != len(next_docs),
              'photo_duplicates': len([p for p in after['photos'] if p['source_key'] == 'samsung']) != len({p['asset_key'] for p in after['photos'] if p['source_key'] == 'samsung'}),
              'readiness_before': before['readiness']['verdict'], 'readiness_after': after['readiness']['verdict'],
              'facts_before': len(before['facts']), 'facts_after': len(after['facts'])}
    result = {**item, 'processed': processed, 'exception': error, 'job_status': job['status'], 'job_message': job['message'],
              **after, 'page_evidence': card_evidence.load(path, pid, 'samsung_page'),
              'document_evidence': card_evidence.load(path, pid, 'samsung_documents'),
              'dealer_evidence': card_evidence.load(path, pid, 'dealer'),
              'events': jobs.list_events(path, job['id']) if job['id'] else [], 'repeat': repeat}
    results[article] = result
    ordered = [results[row["article"]] for row in items if row["article"] in results]
    (root / 'final_pass.json').write_text(json.dumps(ordered, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    print(json.dumps({'article': article, 'status': job['status'], 'readiness': repeat['readiness_after'],
                      'repeat': repeat, 'error': bool(error)}, ensure_ascii=False), flush=True)
