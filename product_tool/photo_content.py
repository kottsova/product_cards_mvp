"""Local image display using the existing bounded, policy-aware byte verifier."""
import hashlib
from pathlib import Path
from threading import Lock
from . import jobs,card_evidence,photo_inventory,photo_metadata

_LOCK=Lock()
TYPES={'JPG':'image/jpeg','JPEG':'image/jpeg','PNG':'image/png','WEBP':'image/webp','GIF':'image/gif','AVIF':'image/avif','TIFF':'image/tiff','BMP':'image/bmp'}

def content(database,product_id,photo_id):
    photo=jobs.get_photo_candidate(database,product_id,photo_id)
    if not photo or photo['kind']=='excluded':raise ValueError('Фото не найдено.')
    if not _LOCK.acquire(timeout=20):raise ValueError('Проверка других фотографий ещё выполняется.')
    try:
        root=Path(database).parent;directory=(root/'official_images').resolve()
        key=photo['source_key']+' / '+photo['asset_key']+' / '+photo['url']
        measurement=(card_evidence.load(database,product_id,'photo_inventory') or {}).get('entries',{}).get(key,{})
        saved=Path(measurement.get('saved_file') or '.')
        data=None
        if saved.is_file() and saved.resolve().parent==directory and saved.stat().st_size<=photo_metadata.MAX_IMAGE_BYTES:
            candidate=saved.read_bytes()
            if hashlib.sha256(candidate).hexdigest()==measurement.get('sha256'):data=candidate
        if data is None:
            measurement=photo_metadata.inspect_saved_photo(photo_inventory.published_origin(photo['url']),photo['source_key'],root/photo_metadata.log_name(photo['source_key']),full_verification=True,save_dir=directory)
            saved=Path(measurement['saved_file'])
            if saved.resolve().parent!=directory or saved.stat().st_size>photo_metadata.MAX_IMAGE_BYTES:raise ValueError('Недопустимый файл фото.')
            data=saved.read_bytes()
            if hashlib.sha256(data).hexdigest()!=measurement['sha256']:raise ValueError('Фото изменилось после проверки.')
            photo_inventory.persist_measurement(database,product_id,photo,measurement)
        content_type=TYPES.get(measurement.get('format','').upper())
        if not content_type:raise ValueError('Формат фото не подтверждён.')
        return data,content_type
    finally:_LOCK.release()
