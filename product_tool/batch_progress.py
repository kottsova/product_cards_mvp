"""Read-only batch projection: latest persisted jobs, never discovery."""
import json
from . import storage
from .job_progress import PHASES

STATUSES={'queued':'В очереди','running':'Выполняется','done':'Завершено','needs_review':'Требует проверки','not_found':'Не найдено','error':'Ошибка'}
READINESS={'export_ready':'Готова','export_ready_with_gaps':'Готова с пробелами','needs_review':'Требует проверки','not_ready':'Не готова'}

def for_batch(database,batch_id):
    with storage._connection(database) as c:
        if not c.execute('SELECT 1 FROM batches WHERE id=?',(batch_id,)).fetchone():return None
        products=c.execute('SELECT id,name,brand,category,search_code,identity_json FROM products WHERE batch_id=? ORDER BY row_number,id',(batch_id,)).fetchall()
        jobs=c.execute('SELECT j.* FROM search_jobs j JOIN products p ON p.id=j.product_id WHERE p.batch_id=? AND j.rowid=(SELECT MAX(x.rowid) FROM search_jobs x WHERE x.product_id=j.product_id)',(batch_id,)).fetchall()
    latest={j['product_id']:dict(j) for j in jobs};rows=[]
    counts=dict(total=len(products),completed=0,running=0,queued=0,review=0,error=0)
    for p in products:
        j=latest.get(p['id'],{});status=j.get('status','');active=status in {'queued','running'}
        r=None if active else j.get('readiness')
        if status in counts:counts[status]+=1
        if status and not active:counts['completed']+=1
        if not active and (status in {'needs_review','not_found'} or r in {'not_ready','needs_review','export_ready_with_gaps'}):counts['review']+=1
        interp=json.loads(p['identity_json'] or '{}').get('input_interpretation',{})
        reason=''
        if status and not active:
            missing=[]
            if not j.get('specs_count'):missing.append('характеристик')
            if not j.get('photos_count'):missing.append('фото')
            reason='Нет подтверждённых '+ '/'.join(missing) if missing else ('Нужна сверка источников' if r in {'not_ready','needs_review','export_ready_with_gaps'} else '')
            if r is None:reason='Результат предыдущей версии; откройте карточку'
        rows.append(dict(id=p['id'],brand=p['brand'],category=p['category'],name=p['name'],model=interp.get('model',''),article=p['search_code'],status=status,
                         status_label=STATUSES.get(status,'Не запускалось'),current_stage=j.get('phase','queued'),progress_label=('Проверка инструкций' if status=='running' and j.get('current_stage')==6 and j.get('phase')=='discovery' else PHASES.get(j.get('phase'),'—')) if status else '—',
                         readiness=r,readiness_label=READINESS.get(r,'—'),reason=reason,specs_count=j.get('specs_count',0),photos_count=j.get('photos_count',0),color=j.get('color') or '—',
                         job_id=j.get('id'),queued_at=j.get('queued_at'),started_at=j.get('started_at'),stage_started_at=j.get('stage_started_at'),finished_at=j.get('finished_at'),final_status=j.get('final_status')))
    return dict(batch_id=batch_id,rows=rows,summary=counts,active=bool(counts['queued'] or counts['running']))
