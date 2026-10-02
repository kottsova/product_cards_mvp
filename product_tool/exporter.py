"""Excel export with Russian resolved values and audit sheets."""
from __future__ import annotations
from io import BytesIO
from pathlib import Path
import re
from openpyxl import Workbook
from openpyxl.styles import Font
from . import attribute_projection, bosch_readiness, jobs, lg_batch, manual_status, photo_metadata, samsung_readiness, storage
from .adapters.lg import lg_base_model
from .lg_identity import document_tied_to_article, photo_tied_to_article
from .display import display_access_error, display_name_ru, display_source, display_status, display_value

def _title(value,used):
    base=re.sub(r"[\[\]:*?/\\]"," ",value or "Категория не определена").strip()[:31] or "Категория"; candidate=base; n=2
    while candidate in used: suffix=f" {n}"; candidate=base[:31-len(suffix)]+suffix; n+=1
    used.add(candidate); return candidate

def _headers(sheet,values):
    sheet.append(values)
    for cell in sheet[1]: cell.font=Font(bold=True)
    sheet.freeze_panes="A2"; sheet.auto_filter.ref=sheet.dimensions


def _photo_cells(item: dict) -> list[str | int]:
    size = item.get("verified_bytes")
    return [
        item.get("verified_width") or "не определено",
        item.get("verified_height") or "не определено",
        photo_metadata.format_file_size(size),
        item.get("verified_format") or "не определено",
    ]

def export_batch(database: Path,batch_id: str)->bytes:
    batch=storage.get_batch(database,batch_id)
    if not batch: raise ValueError("Партия не найдена.")
    book=Workbook(); book.remove(book.active); used=set(); groups={}
    for p in batch["products"]: groups.setdefault(p["category"] or "Категория не определена",[]).append(p)
    for category,products in groups.items():
        sheet=book.create_sheet(_title(category,used)); rows={p["id"]:attribute_projection.final_attribute_rows(database,p["id"]) for p in products}
        keys=sorted({r["normalized_name"] for rr in rows.values() for r in rr},key=lambda k:next(r["display_name"] for rr in rows.values() for r in rr if r["normalized_name"]==k))
        labels={k:next(r["display_name"] for rr in rows.values() for r in rr if r["normalized_name"]==k) for k in keys}
        # Distinct canonical concepts must not acquire an indistinguishable column.
        repeated = {label for label in labels.values() if list(labels.values()).count(label) > 1}
        for key in keys:
            if labels[key] in repeated:
                labels[key] += f" ({key.replace('_', ' ')})"
        _headers(sheet,["Строка","Название","Бренд","Полный артикул","Базовая модель",*[labels[k] for k in keys]])
        for p in products:
            is_lg = lg_batch.is_lg(p)
            resolved = {r["normalized_name"]: value.get("display_value", "")
                        if not is_lg or (value.get("full_sku_confirmed") and not value.get("conflict"))
                        else ""
                        for r in rows[p["id"]] for value in [r.get("resolved") or {}]}
            sheet.append([p["row_number"],(p["name"] or p["search_code"]),p["brand"],p["search_code"],lg_base_model(p["search_code"]) if p["brand"].strip().upper()=="LG" else "",*[resolved.get(k,"") for k in keys]])
    has_lg_global=any(s["source_key"]=="lg_global" for p in batch["products"] for s in jobs.get_source_pages(database,p["id"]))
    has_sulpak_facts=any(f["source_key"]=="sulpak" for p in batch["products"] for f in jobs.get_facts(database,p["id"]))
    has_bosch=any(s["source_key"]=="bosch_home" for p in batch["products"] for s in jobs.get_source_pages(database,p["id"]))
    has_samsung=any(s["source_key"]=="samsung" for p in batch["products"] for s in jobs.get_source_pages(database,p["id"]))  # the Samsung column and sheet exist only when the batch has a Samsung page
    check=book.create_sheet(_title("Проверка источников",used)); _headers(check,["Товар","Полный артикул","Характеристика","LG Казахстан","LG Россия",*(["Sulpak"] if has_sulpak_facts else []),*(["LG other region"] if has_lg_global else []),*(["Samsung"] if has_samsung else []),*(["Bosch Home"] if has_bosch else []),"Итог","Причина","Статус","Все спорные значения"])
    for p in batch["products"]:
        conflict_facts = {}
        for fact in jobs.get_facts(database,p["id"]):
            detail = f"{fact['site_name']}: {fact['raw_value']}"
            if fact.get("section"):
                detail += f" (раздел «{fact['section']}»)"
            values = conflict_facts.setdefault(fact["normalized_name"], [])
            if detail not in values:
                values.append(detail)
        for row in jobs.comparison_rows(database,p["id"]):
            s=row["sources"]; r=row.get("resolved") or {}
            detail = "; ".join(conflict_facts.get(row["normalized_name"], [])) if r.get("conflict") else ""
            label = row["display_name"]
            if r.get("conflict") and label == "Дополнительная характеристика" and row["raw_names"]:
                label = row["raw_names"][0]
            check.append([(p["name"] or p["search_code"]),p["search_code"],label,s.get("lg_kz",{}).get("raw_value",""),s.get("lg_ru",{}).get("raw_value",""),*([s.get("sulpak",{}).get("raw_value","")] if has_sulpak_facts else []),*([s.get("lg_global",{}).get("raw_value","")] if has_lg_global else []),*([s.get("samsung",{}).get("raw_value","")] if has_samsung else []),*([s.get("bosch_home",{}).get("raw_value","")] if has_bosch else []),r.get("display_value",""),r.get("reason",""),r.get("display_status",""),detail])
    source_sheet=book.create_sheet(_title("Источники",used)); _headers(source_sheet,["Товар","Полный артикул","Сайт","Найденная модель","Уровень совпадения","Доказательство","Дата","Ошибка","URL"])
    for p in batch["products"]:
        for s in jobs.get_source_pages(database,p["id"]):
            if s["source_key"] in {"lg_kz_support", "lg_ru_support"}:
                level = {"full_sku":"Связь инструкции с артикулом","base_model":"Поддержка семейства/другого варианта","component_only":"Поддержка одного компонента"}.get(s["match_level"],"Кандидат поддержки")
            else:
                level = {"full_sku":"Полный артикул","code_in_page_text":"Артикул только в тексте страницы","base_model":"Базовая модель","mismatch":"Несоответствие","unknown":"Не проверено"}.get(s["match_level"],s["match_level"])
            if s["source_key"] == "sulpak" and s["match_level"] == "unknown" and s["evidence"] and not s["error"]:
                level = "Комплект не подтверждён"
            source_sheet.append([(p["name"] or p["search_code"]),p["search_code"],s["site_name"],s["found_model"],level,s["evidence"],s["fetched_at"],display_access_error(s["error"]),s["url"]])
    docs=book.create_sheet(_title("Инструкции",used)); _headers(docs,["Товар","Документ","Язык","Дата","Размер","Основной","Модель поддержки","Источник","Прямая ссылка","Связь с артикулом","Тип источника","Статус проверки"])
    photo_columns=["Ширина, px","Высота, px","Размер файла","Формат"]
    photos=book.create_sheet(_title("Фотографии",used)); _headers(photos,["Товар","Источник","Тип","URL","Подтверждение варианта",*photo_columns])
    photo_candidates = None
    for p in batch["products"]:
        source_pages = jobs.get_source_pages(database, p["id"])
        lg = lg_batch.is_lg(p)
        saved_documents = jobs.get_documents(database,p["id"])
        for d in saved_documents:
            tied = document_tied_to_article(p["search_code"], d, source_pages) if lg else True
            docs.append([(p["name"] or p["search_code"]),d["title"],d["language"],d["document_date"],d["size"],"Да" if d["is_primary"] else "Нет",d["support_model"],d["source_url"],d["direct_url"],
                         "Подтверждена" if tied else "PDF проверен, связь с вариантом не подтверждена",
                         "LG" if d["source_key"].startswith("lg_") else display_source(d["source_key"]),
                         "Проверена" if tied else "Не проверена"])
        if lg and not saved_documents:
            status = manual_status.russian_status(database, p["id"], p["search_code"])
            audit = manual_status.completed_search(database, p["id"]) if status == manual_status.NOT_FOUND else None
            support_url = next((item.get("support_url") or item.get("url", "") for item in audit["evidence"] if item.get("kind") == "official_manual_list"), "") if audit else ""
            docs.append([(p["name"] or p["search_code"]), "", "", "", "", "", "", support_url, "", "", "LG" if audit else "", status])
        for item in jobs.get_photo_candidates(database,p["id"],include_excluded=False):
            tied = photo_tied_to_article(item, source_pages) if lg else True
            kind = {"product_gallery":"Товарная галерея","feature":"Особенности и инфографика","marketing":"Маркетинговые материалы"}.get(item["kind"],item["kind"])
            if item["selected"] and tied:
                photos.append([(p["name"] or p["search_code"]),item["site_name"],kind,item["url"],"Подтверждён",*_photo_cells(item)])
            elif item["selected"] and not tied:
                if photo_candidates is None:
                    photo_candidates = book.create_sheet(_title("Фото-кандидаты",used))
                    _headers(photo_candidates,["Товар","Источник","Тип","URL","Выбрано для просмотра","Статус",*photo_columns])
                photo_candidates.append([(p["name"] or p["search_code"]),item["site_name"],kind,item["url"],
                                         "Да" if item["selected"] else "Нет","Связь с артикулом не подтверждена",*_photo_cells(item)])
    if any(lg_batch.is_lg(p) for p in batch["products"]):
        ready=book.create_sheet(_title("Готовность LG",used))
        _headers(ready,["Товар","Полный артикул","Статус задания","Готовность карточки","Проверенные этапы","Причины пробелов","Справочно"])
        for p in batch["products"]:
            if not lg_batch.is_lg(p): continue
            history=jobs.list_jobs(database,p["id"])
            latest=history[0] if history else None
            summary=lg_batch.card_summary(database,p["id"],latest)
            ready.append([(p["name"] or p["search_code"]),p["search_code"],f"{lg_batch.JOB_LABELS.get(latest['status'], latest['status'])} ({latest['status']})" if latest else "Не запускалось",
                          f"{summary['label']} ({summary['verdict']})",
                          ", ".join(jobs.STAGE_NAMES[n] for n in latest["stages"]) if latest else "",
                          " ".join(summary["reasons"]),
                          " ".join(summary.get("advisories",[]))])
    if has_samsung:
        ready=book.create_sheet(_title("Готовность Samsung",used)); _headers(ready,["Товар","Полный артикул","Вердикт","Совпадение страницы","Открыто по варианту","Блокирующие пробелы","Справочно","Инструкция: русский по тексту","Инструкция: связь со страницей","Инструкция: код каталога в тексте","Фото выбрано / найдено","Расхождения с дилером","Открытые проверки","Инструкция: основание принятия","Причины пробелов"])
        for p in batch["products"]:
            if not any(s["source_key"]=="samsung" for s in jobs.get_source_pages(database,p["id"])): continue
            r=samsung_readiness.card_readiness(database,p["id"]); i=r["instruction"]
            yn=lambda v:"" if v is None else ("Да" if v else "Нет")
            named="" if not i["saved"] else "точный код" if i["names_catalog_code_exactly"] else "пометка: "+(i["mark"] or "точный код в PDF не назван")
            ready.append([(p["name"] or p["search_code"]),p["search_code"],r["verdict"],r["page_match_level"],"; ".join(r["open_variant_differences"]),", ".join(r["blocking_gaps"]),", ".join(r["advisory_gaps"]),yn(i["russian_by_text"]),i["tied_by_official_page"] or "",named,f"{r['official_photos_selected']} / {r['official_photos']}","; ".join(d["field"] for d in r["dealer_disputes"]),", ".join(r["open_reviews"]),(i["acceptance_basis"]+(": принята" if i["accepted"] else ": не принята")) if i["acceptance_basis"] else "","; ".join(f"{k}: {v}" for k,v in r["gap_reasons"].items())])
    if has_bosch:
        ready=book.create_sheet(_title("\u0413\u043e\u0442\u043e\u0432\u043d\u043e\u0441\u0442\u044c Bosch Home",used))
        _headers(ready,["\u0422\u043e\u0432\u0430\u0440","\u041a\u043e\u0434 \u043a\u0430\u0442\u0430\u043b\u043e\u0433\u0430","\u0421\u0442\u0430\u0442\u0443\u0441 \u0437\u0430\u0434\u0430\u043d\u0438\u044f","\u0413\u043e\u0442\u043e\u0432\u043d\u043e\u0441\u0442\u044c \u043a\u0430\u0440\u0442\u043e\u0447\u043a\u0438","GTIN","E-Nr","\u0420\u0435\u0432\u0438\u0437\u0438\u044f","\u0425\u0430\u0440\u0430\u043a\u0442\u0435\u0440\u0438\u0441\u0442\u0438\u043a\u0438","\u0424\u043e\u0442\u043e \u0432\u044b\u0431\u0440\u0430\u043d\u043e / \u043d\u0430\u0439\u0434\u0435\u043d\u043e","\u0421\u0435\u043c\u0435\u0439\u0441\u0442\u0432\u043e \u0440\u0443\u043a\u043e\u0432\u043e\u0434\u0441\u0442\u0432\u0430","\u0422\u043e\u0447\u043d\u044b\u0439 \u043a\u043e\u0434 \u0432 PDF","\u041f\u0440\u043e\u0447\u0438\u0435 PDF \u0431\u0435\u0437 \u043f\u0440\u043e\u0432\u0435\u0440\u043a\u0438","\u041f\u0440\u043e\u0431\u0435\u043b\u044b"])
        for p in batch["products"]:
            if not any(src["source_key"]=="bosch_home" for src in jobs.get_source_pages(database,p["id"])): continue
            r=bosch_readiness.card_readiness(database,p["id"])
            history=jobs.list_jobs(database,p["id"])
            status=history[0]["status"] if history else ""
            ready.append([(p["name"] or p["search_code"]),p["search_code"],status,r["verdict"],r["gtin"],r["page_enr"] or "",r["revision_status"],r["official_facts"],f"{r['official_photos_selected']} / {r['official_photos']}",r["manual_family"],"\u0414\u0430" if r["manual_exact_code_in_pdf"] else "\u041d\u0435\u0442",len(r["other_manuals_unverified"]),", ".join(r["blocking_gaps"]+r["advisory_gaps"])])
    for sheet in book.worksheets:
        for col in sheet.columns: sheet.column_dimensions[col[0].column_letter].width=min(60,max(12,max(len(str(c.value or "")) for c in col)+2))
    output=BytesIO(); book.save(output); book.close(); return output.getvalue()