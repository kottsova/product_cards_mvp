"""Final attribute presentation; source facts and resolution stay independent."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from . import bosch_presentation, jobs, lg_presentation


def _refinements(base: str) -> tuple[str, ...]:
    # Only explicit semantic relationships are eligible. A shared substring
    # (Bluetooth Surround, USB camera, ThinQ Wi-Fi) is not such a relationship.
    names = [f"{base}_version", f"версия_{base}"]
    if base == "usb":
        names.extend((
            "usb_ports", "usb_port_count", "usb_порты",
            "количество_портов_usb", "количество_usb_портов",
        ))
    return tuple(dict.fromkeys(names))


def _meaningful(base: dict[str, Any], detail: dict[str, Any]) -> bool:
    presence = base.get("resolved") or {}
    value = detail.get("resolved") or {}
    if (presence.get("selected_value"), presence.get("selected_unit")) != ("true", "bool"):
        return False
    if presence.get("conflict") or value.get("conflict"):
        return False
    if not value.get("selected_value") or value.get("selected_value") in {"true", "false", "unknown", "optional"}:
        return False
    if value.get("selected_unit") in {"bool", "bool_vector", "unknown"}:
        return False
    # An exact-variant presence cannot confer its confidence on a value
    # available only from a base-model page.
    if presence.get("full_sku_confirmed") and not value.get("full_sku_confirmed"):
        return False
    return True


def _port_label(count: str) -> str:
    n = int(count)
    suffix = "порт" if n % 10 == 1 and n % 100 != 11 else (
        "порта" if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14) else "портов"
    )
    return f"{n} {suffix}"


def _shown_value(detail_name: str, value: dict[str, Any], detail: dict[str, Any]) -> str:
    shown = value["display_value"]
    if detail_name in {
        "usb_ports", "usb_port_count", "usb_порты",
        "количество_портов_usb", "количество_usb_портов",
    } and re.fullmatch(r"\d+", str(value["selected_value"])):
        return _port_label(value["selected_value"])
    if detail_name.endswith("_version") or detail_name.startswith("версия_"):
        source = detail["sources"].get(value.get("selected_source", ""), {})
        raw = str(source.get("raw_value") or "")
        # Comparison normalizes 4.0 to 4; presentation can retain the
        # precision printed by the selected official source.
        if re.fullmatch(r"\d+", str(value["selected_value"])):
            written = re.search(r"(?<!\d)(\d+)\.0(?!\d)", raw)
            if written and written.group(1) == str(value["selected_value"]):
                shown = written.group(0)
        return re.sub(r"(?i)wi[-_ ]?fi", "Wi-Fi", shown)
    return shown


def _combined_sources(base: dict[str, Any], detail: dict[str, Any]) -> dict[str, dict[str, Any]]:
    combined = {key: dict(fact) for key, fact in base["sources"].items()}
    for key, fact in detail["sources"].items():
        if key not in combined:
            combined[key] = dict(fact)
            continue
        original = combined[key]
        merged = dict(fact)
        merged["raw_name"] = f"{original['raw_name']}; {fact['raw_name']}"
        merged["raw_value"] = f"{original['raw_value']}; {fact['raw_value']}"
        merged["display_value"] = f"{original['display_value']}; {fact['display_value']}"
        combined[key] = merged
    return combined


def project_final_rows(rows: list[dict[str, Any]], *, exact_ru: bool = False) -> list[dict[str, Any]]:
    """Keep one final value per presence/refinement pair without changing evidence.

    The independent rows remain available through jobs.comparison_rows() and
    get_facts(); this projection is for the card and product Excel sheets.
    """
    by_name = {row["normalized_name"]: row for row in rows}
    projected: dict[str, dict[str, Any]] = {}
    hidden: set[str] = set()
    for base_name, base in by_name.items():
        for detail_name in _refinements(base_name):
            detail = by_name.get(detail_name)
            if detail is None or detail_name in hidden or not _meaningful(base, detail):
                continue
            row = dict(base)
            row["sources"] = _combined_sources(base, detail)
            row["raw_names"] = [*base["raw_names"], *detail["raw_names"]]
            chosen = dict(detail["resolved"])
            chosen["display_value"] = _shown_value(detail_name, chosen, detail)
            chosen["reason"] = (
                chosen["reason"] + " Итоговое значение взято из уточняющего поля; "
                "исходные признаки наличия и значение сохранены раздельно."
            )
            row["resolved"] = chosen
            row["refined_from"] = detail_name
            projected[base_name] = row
            hidden.add(detail_name)
            break
    output = []
    for row in rows:
        name = row["normalized_name"]
        if name in hidden:
            continue
        shown = projected.get(name, row)
        if name in {"bluetooth", "wi_fi", "usb"} and name not in projected:
            value = shown.get("resolved") or {}
            if (value.get("selected_value"), value.get("selected_unit")) == ("true", "bool"):
                shown = dict(shown)
                shown["resolved"] = {**value, "display_value": "Есть"}
        output.append(shown)
    final = []
    for row in output:
        if lg_presentation.classify(row) != "product attribute":
            continue
        row = {**row, "display_name": lg_presentation.canonical_label(row, exact_ru=exact_ru),
               "lg_presentation": True}
        row = lg_presentation.normalize_measure(row)
        split = lg_presentation.split_dimensions(row)
        final.extend(split if split else [lg_presentation.safe_composite_dimensions(row)])
    # Curated same-feature spellings from two LG regions. Merge the visible
    # row only when both independent values agree; raw facts remain intact.
    by_key = {row["normalized_name"]: row for row in final}
    consumed = set()
    for alias, canonical in {"hygienefresh_plus": "hygiene_fresh_plus"}.items():
        left, right = by_key.get(canonical), by_key.get(alias)
        if not left or not right:
            continue
        a, b = left.get("resolved") or {}, right.get("resolved") or {}
        if (a.get("conflict") or b.get("conflict") or
                (a.get("selected_value"), a.get("selected_unit")) !=
                (b.get("selected_value"), b.get("selected_unit")) or
                set(left["sources"]) & set(right["sources"])):
            continue
        left["sources"] = {**left["sources"], **right["sources"]}
        left["raw_names"] = [*left["raw_names"], *right["raw_names"]]
        consumed.add(alias)
    return sorted((row for row in final if row["normalized_name"] not in consumed),
                  key=lambda row: row["display_name"].casefold())


def final_attribute_rows(path: Path, product_id: int) -> list[dict[str, Any]]:
    rows = jobs.comparison_rows(path, product_id)
    product = jobs.get_product(path, product_id)
    if product and product['brand'].strip().casefold()=='hyperx':
        from .hyperx_presentation import project
        return project(rows)
    from .xbox_identity import BRANDS as XBOX_BRANDS
    if product and product['brand'].strip().casefold() in XBOX_BRANDS:
        for row in rows:
            fact=next(iter(row.get('sources',{}).values()),{})
            row['display_name']=fact.get('raw_name') or row['display_name']
            if row['normalized_name']=='product_weight':row['display_name']='Вес товара, кг'
            axes={'product_dimensions__width':'Ширина товара, мм','product_dimensions__height':'Высота товара, мм','product_dimensions__depth':'Глубина товара, мм'}
            if row['normalized_name'] in axes:row['display_name']=axes[row['normalized_name']]
            resolved=row.get('resolved')
            if resolved and resolved.get('selected_unit')=='g' and row['normalized_name']=='product_weight':
                from decimal import Decimal
                resolved['selected_value']=str(Decimal(resolved['selected_value'])/1000);resolved['selected_unit']='kg';resolved['display_value']=resolved['selected_value']+' кг'
            elif resolved and resolved.get('display_value'):
                resolved['display_value']=re.sub(r'\b(?:hours?|hrs?)\b','ч',resolved['display_value'],flags=re.I)
            if resolved and row['normalized_name'] in axes and resolved.get('selected_unit')=='cm':
                from decimal import Decimal
                resolved['selected_value']=str(Decimal(resolved['selected_value'])*10);resolved['selected_unit']='mm';resolved['display_value']=resolved['selected_value']+' мм'
            branded=('Xbox Velocity Architecture','Quick Resume','Smart Delivery','Xbox Wireless','Dolby Atmos','Spatial Sound','Windows Sonic','DTS Headphone:X','RDNA 2','Zen 2','Game Pass Ultimate','Robot White','Carbon Black','Arctic Camo','Galaxy Black','Xbox Series X','Xbox Series S','Xbox One','USB-C','Bluetooth','HDMI','NVME','GDDR6')
            for value in ([resolved] if resolved else [])+list(row.get('sources',{}).values()):
                if value.get('display_value'):
                    for term in branded:value['display_value']=re.sub(re.escape(term),term,value['display_value'],flags=re.I)
        return rows
    from .playstation_identity import BRANDS as PLAYSTATION_BRANDS
    if product and product['brand'].strip().casefold() in PLAYSTATION_BRANDS:
        labels={'product_dimensions__width':'Ширина','product_dimensions__height':'Высота','product_dimensions__depth':'Глубина','product_weight':'Вес','объем_накопителя':'Объём накопителя'}
        for row in rows:
            row['display_name']=labels.get(row['normalized_name'],row['display_name'])
            resolved=row.get('resolved')
            if resolved and resolved.get('display_value'):
                value=resolved['display_value']
                for pattern,replacement in ((r'\bgb\b','ГБ'),(r'\btb\b','ТБ'),(r'\bw\b','Вт'),(r'\bmah\b','мА·ч'),(r'\bApprox\.?','Около'),(r'\bkg\b','кг'),(r'\bg\b','г'),(r'\bV\b','В'),(r'\bA\b','А'),(r'\b(?:hours?|hrs?)\b','ч'),(r'\bminutes?\b','мин')):value=re.sub(pattern,replacement,value,flags=re.I)
                resolved['display_value']=value
        return rows
    if product and product["brand"].strip().upper() == "BOSCH" and any(
            page["source_key"] == "bosch_home" for page in jobs.get_source_pages(path, product_id)):
        return bosch_presentation.project(rows)
    if product and product["brand"].strip().upper() == "JBL":
        from .jbl_presentation import project
        return project(rows)
    if product and product['brand'].strip().casefold() == 'razer':
        from .razer_presentation import project
        return project(rows)
    if product and product["brand"].strip().upper() == "LENOVO":
        from .lenovo_presentation import project
        return project(rows)
    if product and product["brand"].strip().upper() == "SAMSUNG":
        projected = project_final_rows(rows)
        for row in projected:
            if row.get("derived_from"):
                continue
            raw = (row.get("sources", {}).get("samsung") or {}).get("raw_name") or ""
            if re.search(r"[\u0400-\u04ff]", raw):
                label = " ".join(raw.split())
                row["display_name"] = label[:1].upper() + label[1:]
        return projected
    if product and product["brand"].strip().upper() == "LG":
        sources = jobs.get_source_pages(path, product_id)
        exact_ru = any(source["source_key"] == "lg_ru" and source["match_level"] == "full_sku"
                       and not source["error"] for source in sources)
        return project_final_rows(rows, exact_ru=exact_ru)
    return rows
