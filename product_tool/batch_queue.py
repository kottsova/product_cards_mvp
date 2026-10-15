"""User batch selection delegates to the same enqueue used by individual cards."""
from . import jobs,storage,readiness

def default_ids(products):
    chosen={}
    for p in products:chosen.setdefault((p['brand'].strip().casefold(),p['category'].strip().casefold()),p['id'])
    return set(chosen.values())

def enqueue_selected(database,batch_id,product_ids,stages):
    if not product_ids or len(set(product_ids))!=len(product_ids):raise ValueError('Выберите товары без повторов.')
    if not stages or any(s not in jobs.STAGE_NAMES for s in stages):raise ValueError('Выберите этапы проверки.')
    batch=storage.get_batch(database,batch_id)
    if not batch:raise ValueError('Партия не найдена.')
    by_id={p['id']:p for p in batch['products']}
    if any(pid not in by_id for pid in product_ids):raise ValueError('Товар не принадлежит этой партии.')
    with storage._connection(database) as c:
        c.execute('DELETE FROM lg_batch_selection WHERE batch_id=?',(batch_id,))
        c.executemany('INSERT INTO lg_batch_selection(batch_id,product_id) VALUES (?,?)',[(batch_id,pid) for pid in product_ids])
    new=active=0
    for pid in product_ids:
        if any(j['status'] in jobs.ACTIVE for j in jobs.list_jobs(database,pid)):
            active+=1;continue
        try:jobs.enqueue(database,pid,stages);new+=1
        except ValueError:
            if any(j['status'] in jobs.ACTIVE for j in jobs.list_jobs(database,pid)):active+=1
            else:raise
    return dict(selected=len(product_ids),new_jobs=new,already_active=active)

def states(database,products):
    result={}
    for p in products:
        history=jobs.list_jobs(database,p['id']);latest=history[0] if history else None
        result[p['id']]=dict(job=latest,readiness=readiness.card_readiness(database,p['id']) if latest and latest['status'] not in jobs.ACTIVE else None)
    return result
