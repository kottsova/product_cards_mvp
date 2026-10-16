"""Persist real worker operations; numeric legacy stages remain independent."""
from contextvars import ContextVar
from functools import wraps
from . import storage

CURRENT = ContextVar('product_job', default=None)
PHASES = {'queued':'В очереди', 'discovery':'Поиск источников', 'identity':'Проверка модели',
          'extraction_specs':'Характеристики', 'extraction_photos':'Фотографии',
          'normalization':'Нормализация', 'persistence':'Сохранение', 'completed':'Завершено'}

def set_phase(database, job_id, phase):
    if phase not in PHASES:
        raise ValueError('Unknown job phase')
    now = storage._now()
    with storage._connection(database) as c:
        changed = c.execute("UPDATE search_jobs SET phase=?,stage_started_at=?,updated_at=? WHERE id=? AND phase<>? AND status='running'",
                            (phase,now,now,job_id,phase)).rowcount
        if changed:
            c.execute('INSERT INTO job_phase_events(job_id,phase,created_at) VALUES (?,?,?)',(job_id,phase,now))

def active_phase(phase):
    current = CURRENT.get()
    if current:
        set_phase(*current, phase)

def observed(phase):
    def decorate(fn):
        @wraps(fn)
        def call(*args, **kwargs):
            active_phase(phase)
            return fn(*args, **kwargs)
        return call
    return decorate

def snapshot(database, product_id):
    from . import readiness, attribute_projection, photo_inventory, card_evidence, jobs
    from .canonical_attributes import color_result
    product = jobs.get_product(database,product_id)
    rows = attribute_projection.final_attribute_rows(database,product_id)
    photos = photo_inventory.enriched_photos(database,product_id)
    color = color_result(product,rows,jobs.get_source_pages(database,product_id),
                         card_evidence.load(database,product_id,photo_inventory.evidence_kind(product)) or {})
    return dict(readiness=readiness.card_readiness(database,product_id)['verdict'],
                specs_count=sum(bool((r.get('resolved') or {}).get('selected_value')) and not (r.get('resolved') or {}).get('conflict') for r in rows),
                photos_count=sum(p['identity_confirmed'] for p in photos),
                color=color['value'] if color['confirmed'] else '')

def backfill_latest(database):
    """One-time compatibility for terminal jobs; saved evidence, never live I/O.

    Run before the worker starts, keeping the polling endpoint strictly read-only.
    Do not overwrite an active job or label these historical results as a new run.
    """
    with storage._connection(database) as c:
        rows=c.execute("SELECT j.id,j.product_id FROM search_jobs j WHERE j.readiness IS NULL AND j.status NOT IN ('queued','running') AND j.rowid=(SELECT MAX(x.rowid) FROM search_jobs x WHERE x.product_id=j.product_id)").fetchall()
    for row in rows:
        values=snapshot(database,row['product_id'])
        with storage._connection(database) as c:
            c.execute("UPDATE search_jobs SET readiness=?,specs_count=?,photos_count=?,color=? WHERE id=? AND readiness IS NULL AND status NOT IN ('queued','running')",
                      (values['readiness'],values['specs_count'],values['photos_count'],values['color'],row['id']))
