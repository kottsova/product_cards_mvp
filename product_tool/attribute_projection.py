"""Final attribute presentation; source facts and resolution stay independent."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from . import jobs


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


def project_final_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
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
    return sorted(output, key=lambda row: row["display_name"])


def final_attribute_rows(path: Path, product_id: int) -> list[dict[str, Any]]:
    rows = jobs.comparison_rows(path, product_id)
    product = jobs.get_product(path, product_id)
    if product and product["brand"].strip().upper() == "LG":
        return project_final_rows(rows)
    return rows
