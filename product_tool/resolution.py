"""Resolve normalized facts across LG and its trusted fallback suppliers."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Iterable


SUPPLIERS = {"sulpak", "mechta"}


@dataclass(frozen=True)
class ResolvedValue:
    normalized_name: str
    selected_value: str
    selected_unit: str
    status: str
    reason: str
    selected_source: str
    conflict: bool


def _same(facts: list[dict[str, Any]]) -> bool:
    return len({(fact["normalized_value"], fact["unit"]) for fact in facts}) == 1


def resolve_attributes(
    facts: Iterable[dict[str, Any]],
    source_pages: Iterable[dict[str, Any]],
    manual: dict[str, dict[str, Any]] | None = None,
) -> list[ResolvedValue]:
    pages = {page["source_key"]: page for page in source_pages}
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for fact in facts:
        grouped[fact["normalized_name"]].append(fact)
    manual = manual or {}
    results: list[ResolvedValue] = []

    for name in sorted(set(grouped) | set(manual)):
        if name in manual:
            decision = manual[name]
            results.append(ResolvedValue(
                name, decision["selected_value"], decision.get("selected_unit", ""),
                "manual", decision.get("reason") or "Ручной выбор пользователя.",
                "manual", False,
            ))
            continue

        values = grouped[name]
        full_suppliers = [
            fact for fact in values
            if fact["source_key"] in SUPPLIERS
            and pages.get(fact["source_key"], {}).get("match_level") == "full_sku"
        ]
        by_supplier = {}
        for fact in full_suppliers:
            by_supplier.setdefault(fact["source_key"], fact)
        supplier_values = list(by_supplier.values())
        lg_values = [fact for fact in values if fact["source_key"] == "lg"]

        if len(supplier_values) >= 2 and not _same(supplier_values):
            results.append(ResolvedValue(
                name, "", "", "needs_review",
                "Mechta и Sulpak подтверждают полный артикул, но значения расходятся.",
                "", True,
            ))
            continue

        if len(supplier_values) >= 2:
            chosen = supplier_values[0]
            all_values = supplier_values + lg_values
            if lg_values and not _same(all_values):
                reason = (
                    "Mechta и Sulpak подтверждают полный артикул и совпадают; "
                    "их значение имеет приоритет перед базовой моделью LG."
                )
            else:
                reason = "Значение совпало у двух поставщиков полного артикула."
            results.append(ResolvedValue(
                name, chosen["normalized_value"], chosen["unit"],
                "confirmed_two_suppliers", reason, "sulpak+mechta", False,
            ))
            continue

        if len(supplier_values) == 1:
            chosen = supplier_values[0]
            results.append(ResolvedValue(
                name, chosen["normalized_value"], chosen["unit"],
                "confirmed_one_supplier",
                f"Полный артикул подтверждён одним поставщиком: {chosen['site_name']}.",
                chosen["source_key"], False,
            ))
            continue

        if values and _same(values):
            chosen = values[0]
            page = pages.get(chosen["source_key"], {})
            status = "matched" if len(values) > 1 else "needs_review"
            reason = (
                "Нормализованные значения источников совпали."
                if len(values) > 1
                else "Значение найдено только у источника без подтверждения полного артикула."
            )
            if page.get("match_level") == "full_sku" and chosen["source_key"] == "lg":
                status, reason = "full_sku_lg", "Полный артикул найден на LG."
            results.append(ResolvedValue(
                name, chosen["normalized_value"], chosen["unit"],
                status, reason, chosen["source_key"], status == "needs_review",
            ))
            continue

        results.append(ResolvedValue(
            name, "", "", "needs_review",
            "Источники без подтверждения полного артикула расходятся.", "", True,
        ))
    return results