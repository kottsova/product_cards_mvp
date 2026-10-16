"""ZIP of saved selections, verified bytes and published rendition aliases only."""
import hashlib,io,re,time,zipfile
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
from . import jobs, photo_inventory, photo_metadata

def safe_name(value):
    return re.sub(r'[^\w.-]+','_',value,flags=re.UNICODE).strip('._')[:70] or 'product'

def quality_rank(p):
    query=parse_qs(urlsplit(p['url']).query)
    def size(names,fallback):
        for key in names:
            value=query.get(key,[''])[0]
            if value.isdigit():return int(value)
        return fallback or 0
    w=size(('width','w','wid','sw'),p.get('verified_width') or p.get('width'))
    h=size(('height','h','hei','sh'),p.get('verified_height') or p.get('height'))
    return (w*h,max(w,h),not bool(query),bool(p.get('byte_verified')))

def archive(database,product_id,*,inspector=None,clock=time.monotonic,budget_seconds=90):
    product=jobs.get_product(database,product_id)
    if product is None:raise ValueError('Товар не найден.')
    all_photos=photo_inventory.enriched_photos(database,product_id,dedupe=False)
    selected=[max(group,key=quality_rank) for group in photo_inventory.dedupe_groups(all_photos)
              if any(p['selected'] for p in group) and group[0]['kind']!='excluded']
    if not selected:raise ValueError('Сначала выберите фотографии и сохраните выбор.')
    if len(selected)>100:raise ValueError('Выберите не более 100 фотографий за один раз.')
    inspect=inspector or photo_metadata.inspect_saved_photo
    root=Path(database).parent;directory=(root/'official_images').resolve();end=clock()+budget_seconds
    output=io.BytesIO();seen=set();total=0
    prefix=safe_name('_'.join(str(product.get(k) or '') for k in ('brand','model','search_code')))
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_STORED) as z:
        for photo in selected:
            if clock()>=end:raise ValueError('Время загрузки фото истекло. Сохранённые проверки можно использовать при повторе.')
            saved=Path(photo.get('saved_file') or '.')
            cached=saved.is_file() and saved.resolve().parent==directory and saved.stat().st_size<=8000000
            data=saved.read_bytes() if cached else None
            if data is None or hashlib.sha256(data).hexdigest()!=photo.get('sha256'):
                measurement=inspect(photo_inventory.published_origin(photo['url']),photo['source_key'],root/photo_metadata.log_name(photo['source_key']),full_verification=True,save_dir=directory)
                saved=Path(measurement['saved_file'])
                if saved.resolve().parent!=directory or saved.stat().st_size>8000000:raise ValueError('Недопустимый файл фото.')
                data=saved.read_bytes()
                if hashlib.sha256(data).hexdigest()!=measurement['sha256']:raise ValueError('Файл фото изменился после проверки.')
                photo_inventory.persist_measurement(database,product_id,photo,measurement)
                photo={**photo,**measurement}
            digest=hashlib.sha256(data).hexdigest()
            if digest in seen:continue
            seen.add(digest);total+=len(data)
            if total>100000000:raise ValueError('Размер архива превышает 100 МБ; выберите меньше фото.')
            fmt=(photo.get('format') or photo.get('verified_format') or '').lower()
            ext={'jpeg':'jpg','jpg':'jpg','png':'png','webp':'webp','gif':'gif','avif':'avif','tiff':'tiff','bmp':'bmp'}.get(fmt)
            if not ext:raise ValueError('Формат изображения не подтверждён.')
            z.writestr(f'{prefix}_{len(seen):02d}.{ext}',data)
    return prefix+'_photos.zip',output.getvalue()
