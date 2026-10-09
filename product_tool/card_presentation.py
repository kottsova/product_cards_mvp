"""Human-facing card layout built from already stored, independent evidence."""
from __future__ import annotations

from collections import defaultdict
import re
from typing import Any

from .display import display_name_ru, display_source, display_value
from . import bosch_presentation


OFFICIAL = ("lg_ru", "lg_kz", "lg_global", "lg", "samsung", "bosch_home", "lenovo_psref", "lenovo_support", "jbl", "apple", "apple_model")
SUPPORT = ("lg_ru_support", "lg_kz_support")
OFFICIAL += ('xbox_model','xbox_configuration','xbox_hardware')
OFFICIAL += ('razer_model','razer_configuration')


def _clean_label(raw: str) -> str:
    label = " ".join(raw.split()).strip()
    # Footnote definitions printed inside LG attribute labels are explanations,
    # not part of the name. Keep the unmodified string in the raw fact.
    glossary = re.search(r"\s*\(\s*\*?\s*AI\s*[-–—]\s*искусственный интеллект\s*\)", label, flags=re.I)
    if glossary:
        label = label[:glossary.start()].rstrip() + " (ИИ)"
        if label.upper().startswith("AI "):
            label = label[3:]
    return label[:1].upper() + label[1:] if label else ""


def _words(label: str) -> set[str]:
    common = {"искус", "интел", "функ", "режи", "типа", "дани", "упра", "знач"}
    return {word[:4] for word in re.findall(r"[а-яё]{4,}", label.casefold()) if word[:4] not in common}


def _preferred_fact(row: dict[str, Any], pages: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    facts = row["sources"]
    ru = facts.get("lg_ru")
    if ru and pages.get("lg_ru", {}).get("match_level") == "full_sku":
        return ru
    for key in ("lg_kz", "lg_global", "lg", "samsung", "bosch_home", "lg_ru"):
        fact = facts.get(key)
        if fact and re.search(r"[а-яё]", fact.get("raw_name") or "", re.I):
            return fact
    return next((facts[key] for key in OFFICIAL if key in facts), None)


def _related_ru_label(row: dict[str, Any], rows: list[dict[str, Any]], pages: dict[str, dict[str, Any]]) -> str:
    """Prefer a semantically matching exact RU name for a KZ-only fact.

    This affects the visible name only; it never merges attributes or evidence.
    """
    if pages.get("lg_ru", {}).get("match_level") != "full_sku":
        return ""
    kz = row["sources"].get("lg_kz")
    if not kz or "lg_ru" in row["sources"]:
        return ""
    current = _words(kz["raw_name"])
    if not current:
        return ""
    candidates = []
    for other in rows:
        ru = other["sources"].get("lg_ru")
        if not ru or not re.search(r"[а-яё]", ru.get("raw_name") or "", re.I):
            continue
        overlap = current & _words(ru["raw_name"])
        if not overlap:
            continue
        same_value = (kz.get("normalized_value") == ru.get("normalized_value")
                      and kz.get("unit") == ru.get("unit")
                      and kz.get("unit") not in {"bool", "bool_vector", "unknown"})
        ai_pair = (kz.get("unit") == ru.get("unit") == "bool"
                   and kz.get("normalized_value") == ru.get("normalized_value")
                   and ("ai" in kz["raw_name"].casefold() or "\u0438\u0438" in kz["raw_name"].casefold())
                   and ("ai" in ru["raw_name"].casefold() or "\u0438\u0438" in ru["raw_name"].casefold()))
        if same_value or ai_pair:
            candidates.append((len(overlap), ru["raw_name"]))
    return _clean_label(max(candidates)[1]) if len(candidates) == 1 else ""


def _role(category: str, row: dict[str, Any]) -> str:
    """Category-aware presentation role. It does not change quality gates."""
    name = (row["normalized_name"] + " " + row["display_name"]).casefold()
    cat = category.casefold()
    if row.get('razer_presentation'):
        return 'core' if re.search(r'сенсор|чувствитель|частота|кнопк|переключ|подключ|динамик|сопротив|диапазон|микрофон|процессор|видеокарт|память|габарит|ширин|высот|глубин|вес|время работы',name) else 'feature'
    core_terms = ("размер", "габарит", "вес", "масса", "мощност", "емкост", "объем",
                  "объём", "энергопотреб", "напряжен", "уровень шума", "цвет", "питание")
    if "телевиз" in cat:
        core_terms += ("диагонал", "разрешен", "тип экрана", "тип диспле", "тип подсвет",
                       "частота", "hdmi", "usb", "wi-fi", "wi_fi", "bluetooth",
                       "операционн", "система динамиков", "цифров", "аналогов")
    elif any(term in cat for term in ("стирал", "сушил", "washtower")):
        core_terms += ("загрузк", "скорость отжима", "об/мин", "вместим", "класс стир", "класс суш")
    elif "холодиль" in cat:
        core_terms += ("камер", "компрессор", "полок", "мороз", "климатическ")
    elif any(term in cat for term in ("аудио", "саундбар", "музык", "микросистем")):
        core_terms += ("канал", "частот", "акустическ", "bluetooth", "usb")
    feature_terms = (" ai ", "(ии)", "smart diagnosis", "оптимизатор", "game optimizer",
                     "режим", "технолог", "функц", "voice", "thinq", "filmmaker",
                     "wow", "true steam", "turbowash")
    if any(term in name for term in core_terms):
        return "core"
    if any(term in f" {name} " for term in feature_terms):
        return "feature"
    selected = row.get("resolved") or {}
    return "feature" if selected.get("selected_unit") in {"bool", "bool_vector"} else "core"


def _compact_status(row: dict[str, Any]) -> str:
    value = row.get("resolved") or {}
    if value.get("conflict"):
        return "Есть расхождение"
    if value.get("status") == "manual":
        return "Свое значение"
    if value.get("selected_source") == "samsung" and not value.get("full_sku_confirmed"):
        return "\u0412\u0430\u0440\u0438\u0430\u043d\u0442 \u043d\u0435 \u043f\u043e\u0434\u0442\u0432\u0435\u0440\u0436\u0434\u0451\u043d"
    facts = row["sources"]
    if "lg_ru" in facts and "lg_kz" in facts:
        return "Совпадает"
    if "lg_ru" in facts:
        return "Только LG Россия"
    if "lg_global" in facts:
        return "\u0422\u043e\u043b\u044c\u043a\u043e " + display_source("lg_global", row["sources"]["lg_global"].get("site_name", ""))
    if "lg_kz" in facts or "lg" in facts:
        return "Только LG Казахстан"
    selected = value.get("selected_source")
    return f"Только {display_source(selected, facts.get(selected, {}).get('site_name', ''))}" if selected else "Не подтверждено"


def present_card_rows(
    rows: list[dict[str, Any]], facts: list[dict[str, Any]],
    sources: list[dict[str, Any]], category: str,
) -> dict[str, Any]:
    pages = {source["source_key"]: source for source in sources}
    dealer_keys = sorted({key for row in rows for key in row["sources"] if key not in OFFICIAL + SUPPORT}
                         | {key for key, page in pages.items()
                            if key not in OFFICIAL + SUPPORT and page.get("url")
                            and page.get("match_level") not in {"not_needed", "mismatch"}})
    columns = []
    if any(key in pages or any(key in row["sources"] for row in rows) for key in ("lg_ru", "lg_kz", "lg_global", "lg")):
        columns = [("lg_ru", "LG Россия"), ("lg_kz", "LG Казахстан")]
        if "lg_global" in pages or any("lg_global" in row["sources"] for row in rows):
            columns.append(("lg_global", display_source("lg_global", pages.get("lg_global", {}).get("site_name", ""))))
        if any("lg" in row["sources"] for row in rows):
            columns.append(("lg", "LG официальный сайт"))
    else:
        short_names = {"samsung": "Samsung", "bosch_home": "Bosch Home"}
        columns = [(key, short_names.get(key, display_source(key, pages.get(key, {}).get("site_name", ""))))
                   for key in OFFICIAL if key in pages or any(key in row["sources"] for row in rows)]
    columns += [(key, display_source(key, pages.get(key, {}).get("site_name", ""))) for key in dealer_keys]
    raw_by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for fact in facts:
        raw_by_name[fact["normalized_name"]].append(fact)
    groups: dict[str, dict[str, list[dict[str, Any]]]] = {"core": {}, "feature": {}}
    presented: list[dict[str, Any]] = []
    for original in rows:
        row = dict(original)
        if row.get("refined_from") and row.get("resolved"):
            detail_sources = {fact["source_key"] for fact in raw_by_name.get(row["refined_from"], [])}
            row["sources"] = {
                key: ({**fact, "display_value": row["resolved"]["display_value"]}
                      if key in detail_sources else fact)
                for key, fact in row["sources"].items()
            }
        chosen = _preferred_fact(row, pages)
        if chosen:
            official_russian = bool(re.search(r"[а-яё]", chosen.get("raw_name") or "", re.I))
            row["display_name"] = (row["display_name"] if row.get("lg_presentation") or row.get("bosch_presentation") or row.get("lenovo_presentation") or row.get("jbl_presentation") or row.get('razer_presentation') else _related_ru_label(row, rows, pages)
                                   or (_clean_label(chosen["raw_name"]) if official_russian else "")
                                   or display_name_ru(row["normalized_name"], row.get("raw_names", [])))
            section = chosen.get("section") or "Другие характеристики"
        else:
            section = "Другие характеристики"
        if row.get("lg_presentation"):
            from .lg_presentation import dimensions_group
            if dimensions_group(row):
                section = "\u0413\u0430\u0431\u0430\u0440\u0438\u0442\u044b \u0438 \u0432\u0435\u0441"
        if row.get("lg_presentation"):
            from .lg_presentation import canonical_section
            section = canonical_section(section)
        if row.get("bosch_presentation"):
            section = bosch_presentation.section(section)
        if row.get("lenovo_presentation"):
            from . import lenovo_presentation, lg_presentation
            section = "Габариты и вес" if lg_presentation.dimensions_group(row) else lenovo_presentation.section(section)
        if row.get("jbl_presentation"):
            from .jbl_presentation import section as jbl_section
            section = jbl_section(section)
        row["section_name"] = section.strip().lower().capitalize() if section.isupper() and not section.startswith("SMART") else section.strip()
        row["role"] = _role(category, row)
        row["compact_status"] = _compact_status(row)
        row["evidence_facts"] = []
        seen_fact_ids: set[int] = set()
        for key in (row.get("derived_from") or row["normalized_name"], row.get("refined_from")):
            for fact in raw_by_name.get(key, []):
                if fact["id"] not in seen_fact_ids:
                    row["evidence_facts"].append({
                        **fact,
                        "display_source": display_source(fact["source_key"], fact.get("site_name") or ""),
                    })
                    seen_fact_ids.add(fact["id"])
        row["conflict_sides"] = []
        if row.get("resolved") and row["resolved"].get("conflict"):
            for fact in row["evidence_facts"]:
                shown = (f"{fact['display_source']}, "
                         f"{fact.get('section') or 'без раздела'} → "
                         f"{display_value(fact['normalized_value'], fact['unit'])}")
                if shown not in row["conflict_sides"]:
                    row["conflict_sides"].append(shown)
        presented.append(row)
    # Two exact official pages can spell the same concept differently. Combine
    # only the visible rows when their chosen Russian label and normalized
    # values agree. The stored facts and resolved decisions remain separate.
    consumed: set[int] = set()
    if (pages.get("lg_ru", {}).get("match_level") == "full_sku"
            and pages.get("lg_kz", {}).get("match_level") == "full_sku"):
        for kz in presented:
            if set(kz["sources"]) != {"lg_kz"} or (kz.get("resolved") or {}).get("conflict"):
                continue
            if (kz.get("resolved") or {}).get("status") == "manual":
                continue
            kz_fact = kz["sources"]["lg_kz"]
            matches = [
                ru for ru in presented
                if set(ru["sources"]) == {"lg_ru"}
                and ru["display_name"] == kz["display_name"]
                and not (ru.get("resolved") or {}).get("conflict")
                and (ru.get("resolved") or {}).get("status") != "manual"
                and ru["sources"]["lg_ru"].get("normalized_value") == kz_fact.get("normalized_value")
                and ru["sources"]["lg_ru"].get("unit") == kz_fact.get("unit")
            ]
            if len(matches) == 1:
                ru = matches[0]
                ru["sources"] = {**ru["sources"], "lg_kz": kz_fact}
                ru["evidence_facts"] = [*ru["evidence_facts"], *kz["evidence_facts"]]
                ru["compact_status"] = _compact_status(ru)
                consumed.add(id(kz))
    for row in presented:
        if id(row) not in consumed:
            groups[row["role"]].setdefault(row["section_name"], []).append(row)
    for role in groups:
        groups[role] = {section: sorted(items, key=lambda item: item["display_name"].casefold())
                        for section, items in sorted(groups[role].items(), key=lambda pair: pair[0].casefold())}
    return {"columns": columns, "groups": groups,
            "count": sum(len(items) for sections in groups.values() for items in sections.values())}
