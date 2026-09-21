"""Resolve normalized facts across official LG regions and trusted suppliers."""
from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Iterable

SUPPLIERS={"sulpak","mechta"}
OFFICIAL={"lg","lg_kz","lg_ru"}

@dataclass(frozen=True)
class ResolvedValue:
    normalized_name: str
    selected_value: str
    selected_unit: str
    status: str
    reason: str
    selected_source: str
    conflict: bool
    full_sku_confirmed: bool=False

def _signature(fact): return fact["normalized_value"],fact["unit"]
def _different(values): return len(values)>=2 and len({_signature(x) for x in values})>1

def resolve_attributes(facts: Iterable[dict[str,Any]], source_pages: Iterable[dict[str,Any]], manual=None):
    pages={p["source_key"]:p for p in source_pages}; grouped=defaultdict(list)
    for fact in facts: grouped[fact["normalized_name"]].append(fact)
    manual=manual or {}; results=[]
    for name in sorted(set(grouped)|set(manual)):
        if name in manual:
            d=manual[name]; results.append(ResolvedValue(name,d["selected_value"],d.get("selected_unit", ""),"manual",d.get("reason") or "Ручной выбор пользователя.","manual",False,True)); continue
        values=grouped[name]
        suppliers=[]; seen=set()
        for f in values:
            if f["source_key"] in SUPPLIERS and pages.get(f["source_key"],{}).get("match_level")=="full_sku" and f["source_key"] not in seen:
                suppliers.append(f); seen.add(f["source_key"])
        official=[f for f in values if f["source_key"] in OFFICIAL]
        if _different(suppliers):
            results.append(ResolvedValue(name,"","","needs_review","Mechta и Sulpak подтверждают полный артикул, но значения расходятся.","",True,True)); continue
        if suppliers:
            chosen=suppliers[0]
            if len(suppliers)>=2:
                status="confirmed_two_suppliers"; source="sulpak+mechta"; reason="Совпало у двух поставщиков полного артикула."
            else:
                status="confirmed_one_supplier"; source=chosen["source_key"]; reason=f"Полный артикул подтверждён одним поставщиком: {chosen['site_name']}."
            if official and any(_signature(x)!=_signature(chosen) for x in official): reason += " Значение полного артикула имеет приоритет перед базовой моделью LG."
            results.append(ResolvedValue(name,chosen["normalized_value"],chosen["unit"],status,reason,source,False,True)); continue
        if official:
            if _different(official):
                results.append(ResolvedValue(name,"","","official_regions_conflict","Различие официальных регионов: LG Россия и LG Казахстан дали разные значения.","",True,False))
            else:
                chosen=official[0]
                results.append(ResolvedValue(name,chosen["normalized_value"],chosen["unit"],"official_base_only","Найдено только у базовой модели LG; источником полного артикула не подтверждено.",chosen["source_key"],False,False))
            continue
        if _different(values):
            results.append(ResolvedValue(name,"","","needs_review","Минимум два источника дали разные нормализованные значения.","",True,False))
        elif values:
            chosen=values[0]; results.append(ResolvedValue(name,chosen["normalized_value"],chosen["unit"],"needs_review","Значение найдено только в одном неподтверждённом источнике.",chosen["source_key"],False,False))
    return results