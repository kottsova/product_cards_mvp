"""Excel export with Russian resolved values and audit sheets."""
from __future__ import annotations
from io import BytesIO
from pathlib import Path
import re
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment
from . import jbl_pipeline, lenovo_pipeline, lenovo_presentation, attribute_projection, bosch_presentation, bosch_readiness, card_evidence, jobs, lg_batch, lg_presentation, manual_status, photo_metadata, samsung_readiness, storage
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
                        if not (is_lg or p["brand"].strip().upper() in {"SAMSUNG", "LENOVO"}) or (value.get("full_sku_confirmed") and not value.get("conflict"))
                        else ""
                        for r in rows[p["id"]] for value in [r.get("resolved") or {}]}
            sheet.append([p["row_number"],(p["name"] or p["search_code"]),p["brand"],p["search_code"],lg_base_model(p["search_code"]) if p["brand"].strip().upper()=="LG" else "",*[resolved.get(k,"") for k in keys]])
    has_lg=any(lg_batch.is_lg(p) for p in batch["products"])
    has_lg_global=any(s["source_key"]=="lg_global" for p in batch["products"] for s in jobs.get_source_pages(database,p["id"]))
    has_sulpak_facts=any(f["source_key"]=="sulpak" for p in batch["products"] for f in jobs.get_facts(database,p["id"]))
    has_bosch=any(s["source_key"]=="bosch_home" for p in batch["products"] for s in jobs.get_source_pages(database,p["id"]))
    has_samsung=any(s["source_key"]=="samsung" for p in batch["products"] for s in jobs.get_source_pages(database,p["id"]))  # the Samsung column and sheet exist only when the batch has a Samsung page
    check=book.create_sheet(_title("Проверка источников",used)); _headers(check,["Товар","Полный артикул","Характеристика",*(["LG Казахстан","LG Россия"] if has_lg else []),*(["Sulpak"] if has_sulpak_facts else []),*(["LG other region"] if has_lg_global else []),*(["Samsung"] if has_samsung else []),*(["Bosch Home"] if has_bosch else []),"Итог","Причина","Статус","Все спорные значения","\u0418\u0441\u0445\u043e\u0434\u043d\u044b\u0435 \u043d\u0430\u0437\u0432\u0430\u043d\u0438\u044f"])
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
            s=row["sources"]; r=(lg_presentation.safe_composite_dimensions(row).get("resolved")
                                  if lg_batch.is_lg(p) else row.get("resolved")) or {}
            detail = "; ".join(conflict_facts.get(row["normalized_name"], [])) if r.get("conflict") else ""
            label = (bosch_presentation.label(row) if p["brand"].strip().upper() == "BOSCH" else row["display_name"])
            if r.get("conflict") and label == "Дополнительная характеристика" and row["raw_names"]:
                label = row["raw_names"][0]
            check.append([(p["name"] or p["search_code"]),p["search_code"],label,*([s.get("lg_kz",{}).get("raw_value",""),s.get("lg_ru",{}).get("raw_value","")] if has_lg else []),*([s.get("sulpak",{}).get("raw_value","")] if has_sulpak_facts else []),*([s.get("lg_global",{}).get("raw_value","")] if has_lg_global else []),*([s.get("samsung",{}).get("raw_value","")] if has_samsung else []),*([s.get("bosch_home",{}).get("raw_value","")] if has_bosch else []),r.get("display_value",""),r.get("reason",""),r.get("display_status",""),detail, "; ".join(dict.fromkeys(row["raw_names"]))])
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
        samsung = p["brand"].strip().upper() == "SAMSUNG"
        jbl = p["brand"].strip().upper() == "JBL"
        jbl_evidence = card_evidence.load(database,p["id"],"jbl") if jbl else None
        lenovo = p["brand"].strip().upper() == "LENOVO"
        lenovo_evidence = card_evidence.load(database,p["id"],"lenovo") if lenovo else None
        saved_documents = (manual_status.effective_documents(database,p["id"],p["search_code"])
                           if lg else jobs.get_documents(database,p["id"]))
        for d in saved_documents:
            tied = (d.get("identity_confirmed", False) if lg else
                    bosch_presentation.document_verified(d, card_evidence.load(database,p["id"],"bosch_home"), source_pages)
                    if p["brand"].strip().upper() == "BOSCH" else
                    samsung_readiness.document_verified(d, card_evidence.load(database,p["id"],"samsung_documents"))
                    if samsung else lenovo_pipeline.document_verified(d, lenovo_evidence) if lenovo else jbl_pipeline.document_verified(d, jbl_evidence) if jbl else True)
            docs.append([(p["name"] or p["search_code"]),d["title"],d["language"],d["document_date"],d["size"],"Да" if d["is_primary"] else "Нет",d["support_model"],d["source_url"],d["direct_url"],
                         "Подтверждена" if tied else "PDF проверен, связь с вариантом не подтверждена",
                         "LG" if d["source_key"].startswith("lg_") else display_source(
                             d["source_key"], next((page["site_name"] for page in source_pages
                                                    if page["source_key"] == d["source_key"]), "")),
                         "Проверена" if tied else "Не проверена"])
        if lg or (samsung and manual_status.completed_search(database,p["id"])):
            status = manual_status.russian_status(database, p["id"], p["search_code"])
            if status != manual_status.VERIFIED:
                audit = manual_status.completed_search(database, p["id"])
                support_url = next((item.get("support_url") or item.get("url", "")
                                    for item in audit["evidence"] if item.get("official")), "") if audit else ""
                if samsung and not support_url:
                    support_url = (card_evidence.load(database,p["id"],"samsung_documents") or {}).get("support", {}).get("url", "")
                reason = manual_status.unchecked_reason(database, p["id"], p["search_code"])
                docs.append([(p["name"] or p["search_code"]), "", "", "", "", "", "",
                             support_url, "", reason, "LG" if lg and audit else "Samsung" if samsung else "", status])
        for item in jobs.get_photo_candidates(database,p["id"],include_excluded=p["brand"].strip().upper() in ("BOSCH", "SAMSUNG")):
            tied = photo_tied_to_article(item, source_pages) if lg else samsung_readiness.photo_verified(item, source_pages, p["search_code"]) if samsung else lenovo_pipeline.photo_verified(item, lenovo_evidence) if lenovo else jbl_pipeline.photo_verified(item, jbl_evidence) if jbl else True
            kind = {"product_gallery":"Товарная галерея","feature":"Особенности и инфографика","marketing":"Маркетинговые материалы"}.get(item["kind"],item["kind"])
            if item["kind"] == "excluded" and p["brand"].strip().upper() in ("BOSCH", "SAMSUNG"):
                if photo_candidates is None:
                    photo_candidates = book.create_sheet(_title("Фото-кандидаты",used))
                    _headers(photo_candidates,["Товар","Источник","Тип","URL","Выбрано для просмотра","Статус",*photo_columns])
                reason = {"base_model_only": "Только базовая модель",
                          "not_model_bound": "Нет доказанной связи с точной моделью"}.get(
                              item["excluded_reason"], item["excluded_reason"] or "Исключено")
                photo_candidates.append([(p["name"] or p["search_code"]),item["site_name"],
                                         "Исключённый кандидат",item["url"],"Нет",reason,*_photo_cells(item)])
                continue
            if item["selected"] and tied:
                photos.append([(p["name"] or p["search_code"]),item["site_name"],kind,item["url"],"Цвет подтверждён" if lenovo else "Подтверждён",*_photo_cells(item)])
            elif item["selected"] and not tied:
                if photo_candidates is None:
                    photo_candidates = book.create_sheet(_title("Фото-кандидаты",used))
                    _headers(photo_candidates,["Товар","Источник","Тип","URL","Выбрано для просмотра","Статус",*photo_columns])
                photo_candidates.append([(p["name"] or p["search_code"]),item["site_name"],kind,item["url"],
                                         "Да" if item["selected"] else "Нет","Связь с артикулом не подтверждена",*_photo_cells(item)])
            elif (samsung or lenovo or jbl) and item["kind"] != "excluded":
                if photo_candidates is None:
                    photo_candidates = book.create_sheet(_title("Фото-кандидаты",used))
                    _headers(photo_candidates,["Товар","Источник","Тип","URL","Выбрано для просмотра","Статус",*photo_columns])
                photo_candidates.append([(p["name"] or p["search_code"]),item["site_name"],kind,item["url"],
                                         "Нет","Связь с артикулом не подтверждена" if not tied else "Не выбрано",*_photo_cells(item)])
    lenovo_products = [p for p in batch["products"] if p["brand"].strip().upper() == "LENOVO"]
    if lenovo_products:
        candidates=book.create_sheet(_title("Конфигурации-кандидаты",used))
        _headers(candidates,["Товар","Артикул","Раздел","Исходное поле","Значение","Связь","Причина"])
        manual_candidates=book.create_sheet(_title("Документы-кандидаты Lenovo",used))
        _headers(manual_candidates,["Товар","Артикул","Тип","Название","Язык","URL","Связь","Проверка"])
        ready=book.create_sheet(_title("Готовность Lenovo",used))
        _headers(ready,["Товар","Артикул","Готовность","Пробелы","Русская инструкция"])
        for p in lenovo_products:
            ev=card_evidence.load(database,p["id"],"lenovo") or {}
            for c in ev.get("configuration_candidates",[]):
                candidates.append([p["name"],p["search_code"],lenovo_presentation.section(c["section"]),c["raw_label"],c["value"],lenovo_presentation.SCOPES.get(c["scope"],c["scope"]),"Условное значение; требуется проверка для полного артикула"])
            for d in ev.get("manuals",[]):
                manual_candidates.append([p["name"],p["search_code"],d["type"],d["title"],d["language"],d["url"],lenovo_presentation.SCOPES.get(d["relation"],d["relation"]),"Проверена" if d["verified"] else "Не проверена"])
            r=lenovo_pipeline.card_readiness(database,p["id"])
            ready.append([p["name"],p["search_code"],lenovo_presentation.VERDICTS.get(r["verdict"],r["verdict"]),"; ".join(lenovo_presentation.gap_labels(r)),r["manual_status"]])
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
        ready=book.create_sheet(_title("Готовность Samsung",used))
        include_dealer = any(samsung_readiness.card_readiness(database, p["id"])["dealer_disputes"] for p in batch["products"] if p["brand"].strip().upper() == "SAMSUNG")
        headers=["Товар","Полный артикул","Вердикт","Совпадение страницы","Открыто по варианту","Блокирующие пробелы","Справочно","Инструкция: русский по тексту","Инструкция: связь со страницей","Инструкция: код каталога в тексте","Фото выбрано / найдено","Расхождения с дилером","Открытые проверки","Инструкция: основание принятия","Причины пробелов"]
        if not include_dealer: headers.pop(11)
        _headers(ready, headers)
        for p in batch["products"]:
            if not any(s["source_key"]=="samsung" for s in jobs.get_source_pages(database,p["id"])): continue
            r=samsung_readiness.card_readiness(database,p["id"]); i=r["instruction"]
            yn=lambda v:"" if v is None else ("Да" if v else "Нет")
            named="" if not i["saved"] else "точный код" if i["names_catalog_code_exactly"] else "пометка: "+(i["mark"] or "точный код в PDF не назван")
            row=[(p["name"] or p["search_code"]),p["search_code"],r["verdict"],r["page_match_level"],"; ".join(r["open_variant_differences"]),", ".join(r["blocking_gaps"]),", ".join(r["advisory_gaps"]),yn(i["russian_by_text"]),i["tied_by_official_page"] or "",named,f"{r['official_photos_selected']} / {r['official_photos']}","; ".join(d["field"] for d in r["dealer_disputes"]),", ".join(r["open_reviews"]),(i["acceptance_basis"]+(": принята" if i["accepted"] else ": не принята")) if i["acceptance_basis"] else "","; ".join(f"{k}: {v}" for k,v in r["gap_reasons"].items())]
            if not include_dealer: row.pop(11)
            ready.append(row)
    if has_bosch:
        ready=book.create_sheet(_title("\u0413\u043e\u0442\u043e\u0432\u043d\u043e\u0441\u0442\u044c Bosch Home",used))
        _headers(ready,["\u0422\u043e\u0432\u0430\u0440","\u041a\u043e\u0434 \u043a\u0430\u0442\u0430\u043b\u043e\u0433\u0430","\u0421\u0442\u0430\u0442\u0443\u0441 \u0437\u0430\u0434\u0430\u043d\u0438\u044f","\u0413\u043e\u0442\u043e\u0432\u043d\u043e\u0441\u0442\u044c \u043a\u0430\u0440\u0442\u043e\u0447\u043a\u0438","GTIN","E-Nr","\u0420\u0435\u0432\u0438\u0437\u0438\u044f","\u0425\u0430\u0440\u0430\u043a\u0442\u0435\u0440\u0438\u0441\u0442\u0438\u043a\u0438","\u0424\u043e\u0442\u043e \u0432\u044b\u0431\u0440\u0430\u043d\u043e / \u043d\u0430\u0439\u0434\u0435\u043d\u043e","\u0421\u0435\u043c\u0435\u0439\u0441\u0442\u0432\u043e \u0440\u0443\u043a\u043e\u0432\u043e\u0434\u0441\u0442\u0432\u0430","\u0422\u043e\u0447\u043d\u044b\u0439 \u043a\u043e\u0434 \u0432 PDF","\u041f\u0440\u043e\u0447\u0438\u0435 PDF \u0431\u0435\u0437 \u043f\u0440\u043e\u0432\u0435\u0440\u043a\u0438","\u041f\u0440\u043e\u0431\u0435\u043b\u044b"])
        for p in batch["products"]:
            if not any(src["source_key"]=="bosch_home" for src in jobs.get_source_pages(database,p["id"])): continue
            r=bosch_readiness.card_readiness(database,p["id"])
            history=jobs.list_jobs(database,p["id"])
            status=history[0]["status"] if history else ""
            ready.append([(p["name"] or p["search_code"]),p["search_code"],status,r["verdict"],r["gtin"],r["page_enr"] or "",r["revision_status"],r["official_facts"],f"{r['official_photos_selected']} / {r['official_photos']}",r["manual_family"],"\u0414\u0430" if r["manual_exact_code_in_pdf"] else "\u041d\u0435\u0442",len(r["other_manuals_unverified"]),", ".join(r["blocking_gaps"]+r["advisory_gaps"])])
    jbl_products = [p for p in batch["products"] if p["brand"].strip().upper() == "JBL"]
    if jbl_products:
        ready_jbl=book.create_sheet(_title("Готовность JBL",used))
        _headers(ready_jbl,["Товар","Полный артикул","Готовность","Пробелы","Русская инструкция","Связь модели","Связь варианта"])
        candidates_jbl=book.create_sheet(_title("Характеристики-кандидаты JBL",used))
        _headers(candidates_jbl,["Товар","Раздел","Исходное поле","Значение","Причина"])
        documents_jbl=book.create_sheet(_title("Документы-кандидаты JBL",used))
        _headers(documents_jbl,["Товар","Тип","Название","URL","Связь","Проверка"])
        for p in jbl_products:
            ev=card_evidence.load(database,p["id"],"jbl") or {};r=jbl_pipeline.card_readiness(database,p["id"])
            ready_jbl.append([p["name"],p["search_code"],jbl_pipeline.VERDICTS[r["verdict"]],"; ".join(jbl_pipeline.GAPS[g] for g in r["gaps"]),r["manual_status"],r["model_identity"],r["variant_identity"]])
            for c in ev.get("rejected_specs",[]):candidates_jbl.append([p["name"],c["section"],c["raw_label"],c["value"],c["reason"]])
            for d in ev.get("manuals",[]):documents_jbl.append([p["name"],d["type"],d["title"],d["url"],d["relation"],"Проверена" if d["verified"] else "Не проверена"])
    apple_products = [p for p in batch["products"] if p["brand"].strip().upper() == "APPLE"]
    if apple_products:
        from . import apple_pipeline
        ready_apple=book.create_sheet(_title("Готовность Apple",used))
        _headers(ready_apple,["Товар","Артикул","Готовность","Модель","Конфигурация","Вариант","Русская инструкция","Пробелы"])
        candidates_apple=book.create_sheet(_title("Варианты-кандидаты Apple",used))
        _headers(candidates_apple,["Товар","Раздел","Исходное поле","Значение","Причина"])
        for p in apple_products:
            ev=card_evidence.load(database,p["id"],"apple") or {};r=apple_pipeline.card_readiness(database,p["id"]);ident=r["identity"]
            ready_apple.append([p["name"],p["search_code"],"Готова" if r["verdict"]=="export_ready" else "Не готова",ident.get("model","unproven"),ident.get("configuration","unproven"),ident.get("variant","unproven"),r["manual_status"],"; ".join(r["blocking_gaps"])])
            for c in ev.get("configuration_candidates",[]):candidates_apple.append([p["name"],c["section"],c["raw_label"],c["value"],c["reason"]])
    for sheet in book.worksheets:
        for col in sheet.columns: sheet.column_dimensions[col[0].column_letter].width=min(60,max(12,max(len(str(c.value or "")) for c in col)+2))
    if lenovo_products:
        from math import ceil
        for sheet in (candidates, manual_candidates, ready):
            for row in sheet.iter_rows():
                lines=1
                for cell in row:
                    cell.alignment=Alignment(wrap_text=True,vertical="top")
                    width=sheet.column_dimensions[cell.column_letter].width or 12
                    lines=max(lines,ceil(len(str(cell.value or ""))/max(8,width-2)))
                sheet.row_dimensions[row[0].row].height=max(22,16*lines)
    output=BytesIO(); book.save(output); book.close(); return output.getvalue()
