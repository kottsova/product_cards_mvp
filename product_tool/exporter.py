"""Excel export with Russian resolved values and audit sheets."""
from __future__ import annotations
from io import BytesIO
from pathlib import Path
import re
from openpyxl import Workbook
from openpyxl.styles import Font
from . import jobs, storage
from .adapters.lg import lg_base_model
from .display import display_name_ru, display_source, display_status, display_value

def _title(value,used):
    base=re.sub(r"[\[\]:*?/\\]"," ",value or "Категория не определена").strip()[:31] or "Категория"; candidate=base; n=2
    while candidate in used: suffix=f" {n}"; candidate=base[:31-len(suffix)]+suffix; n+=1
    used.add(candidate); return candidate

def _headers(sheet,values):
    sheet.append(values)
    for cell in sheet[1]: cell.font=Font(bold=True)
    sheet.freeze_panes="A2"; sheet.auto_filter.ref=sheet.dimensions

def export_batch(database: Path,batch_id: str)->bytes:
    batch=storage.get_batch(database,batch_id)
    if not batch: raise ValueError("Партия не найдена.")
    book=Workbook(); book.remove(book.active); used=set(); groups={}
    for p in batch["products"]: groups.setdefault(p["category"] or "Категория не определена",[]).append(p)
    for category,products in groups.items():
        sheet=book.create_sheet(_title(category,used)); rows={p["id"]:jobs.comparison_rows(database,p["id"]) for p in products}
        keys=sorted({r["normalized_name"] for rr in rows.values() for r in rr},key=lambda k:next(r["display_name"] for rr in rows.values() for r in rr if r["normalized_name"]==k))
        labels={k:next(r["display_name"] for rr in rows.values() for r in rr if r["normalized_name"]==k) for k in keys}
        _headers(sheet,["Строка","Название","Бренд","Полный артикул","Базовая модель",*[labels[k] for k in keys]])
        for p in products:
            resolved={r["normalized_name"]:(r.get("resolved") or {}).get("display_value","") for r in rows[p["id"]]}
            sheet.append([p["row_number"],p["name"],p["brand"],p["search_code"],lg_base_model(p["search_code"]) if p["brand"].strip().upper()=="LG" else "",*[resolved.get(k,"") for k in keys]])
    check=book.create_sheet(_title("Проверка источников",used)); _headers(check,["Товар","Полный артикул","Характеристика","LG Казахстан","LG Россия","Mechta","Sulpak","Итог","Причина","Статус"])
    for p in batch["products"]:
        for row in jobs.comparison_rows(database,p["id"]):
            s=row["sources"]; r=row.get("resolved") or {}
            check.append([p["name"],p["search_code"],row["display_name"],s.get("lg_kz",{}).get("raw_value",""),s.get("lg_ru",{}).get("raw_value",""),s.get("mechta",{}).get("raw_value",""),s.get("sulpak",{}).get("raw_value",""),r.get("display_value",""),r.get("reason",""),r.get("display_status","")])
    source_sheet=book.create_sheet(_title("Источники",used)); _headers(source_sheet,["Товар","Полный артикул","Сайт","Найденная модель","Уровень совпадения","Доказательство","Дата","Ошибка","URL"])
    for p in batch["products"]:
        for s in jobs.get_source_pages(database,p["id"]): source_sheet.append([p["name"],p["search_code"],s["site_name"],s["found_model"],{"full_sku":"Полный артикул","base_model":"Базовая модель","mismatch":"Несоответствие","unknown":"Не проверено"}.get(s["match_level"],s["match_level"]),s["evidence"],s["fetched_at"],s["error"],s["url"]])
    docs=book.create_sheet(_title("Инструкции",used)); _headers(docs,["Товар","Документ","Язык","Дата","Размер","Основной","Модель поддержки","Источник","Прямая ссылка"])
    photos=book.create_sheet(_title("Фотографии",used)); _headers(photos,["Товар","Источник","Тип","URL"])
    for p in batch["products"]:
        for d in jobs.get_documents(database,p["id"]): docs.append([p["name"],d["title"],d["language"],d["document_date"],d["size"],"Да" if d["is_primary"] else "Нет",d["support_model"],d["source_url"],d["direct_url"]])
        for item in jobs.get_photo_candidates(database,p["id"],include_excluded=False):
            if item["selected"]: photos.append([p["name"],item["site_name"],{"product_gallery":"Товарная галерея","feature":"Особенности и инфографика","marketing":"Маркетинговые материалы"}.get(item["kind"],item["kind"]),item["url"]])
    for sheet in book.worksheets:
        for col in sheet.columns: sheet.column_dimensions[col[0].column_letter].width=min(60,max(12,max(len(str(c.value or "")) for c in col)+2))
    output=BytesIO(); book.save(output); book.close(); return output.getvalue()