"""Resolve normalized facts across official LG regions and trusted suppliers."""
from __future__ import annotations
import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Iterable

SUPPLIERS={"sulpak"}
OFFICIAL={"lg","lg_kz","lg_ru","lg_global","hyperx","samsung","bosch_home","lenovo_support","lenovo_psref","jbl"}

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

def _canonical_value(value):
    """Comparison key only (display keeps the normalized value): spacing, thousands separators, 'шт.' and the multiplication sign
    are formatting, so "1шт" and "1 шт.", "3,840 x 2,160" and "3840 x 2160", "60Гц" and "60 Гц" are the same value."""
    text=re.sub(r"(?<=\d),(?=\d{3}(?!\d))","",str(value).casefold())
    text=re.sub(r"\s+","",text).replace("×","x")
    if re.search(r"\d[хx]\d", text):
        text=text.replace("х","x")
    text=re.sub(r"шт\.","шт",text)
    text=text.replace("(r/l)","(п/л)").replace("(u/d)","(в/н)").replace("меньше","менее")  # the same wording in the two site languages
    text=text.replace("~","-").replace("mhz","мгц").replace("khz","кгц").replace("ghz","ггц")  # a range written 87.5 ~ 108 MHz or 87.5 - 108 МГц
    text=re.sub(r"(?<=\d)hz","гц",text)
    return re.sub(r"(?<=\d)(?:\"|мм)$","",text)  # a unit mark printed after the number when the field name already carries the unit
def _signature(fact): return _canonical_value(fact["normalized_value"]),fact["unit"]
def _different(values): return len(values)>=2 and len({_signature(x) for x in values})>1

def resolve_attributes(facts: Iterable[dict[str,Any]], source_pages: Iterable[dict[str,Any]], manual=None):
    pages={p["source_key"]:p for p in source_pages}; grouped=defaultdict(list)
    for fact in facts:
        if fact["normalized_value"] == "unknown" and fact["unit"] == "unknown":
            continue
        grouped[fact["normalized_name"]].append(fact)
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
        if (name == "color" or name.startswith("color__") or name.startswith("\u043e\u0442\u0434\u0435\u043b\u043a\u0430_")) and any(key in pages for key in ("lg", "lg_kz", "lg_ru", "lg_global")):
            exact = [f for f in values if pages.get(f["source_key"], {}).get("match_level") in {"full_sku", "model_and_code_confirmed"}]
            if not exact:
                reason = "\u0426\u0432\u0435\u0442 \u0431\u0430\u0437\u043e\u0432\u043e\u0439 \u043c\u043e\u0434\u0435\u043b\u0438 \u043d\u0435 \u043f\u043e\u0434\u0442\u0432\u0435\u0440\u0436\u0434\u0430\u0435\u0442 \u0446\u0432\u0435\u0442 \u043f\u043e\u043b\u043d\u043e\u0433\u043e \u0430\u0440\u0442\u0438\u043a\u0443\u043b\u0430."
                if _different(official):
                    results.append(ResolvedValue(name, "", "", "official_regions_conflict", reason + " \u0420\u0435\u0433\u0438\u043e\u043d\u044b \u0434\u0430\u043b\u0438 \u0440\u0430\u0437\u043d\u044b\u0435 \u0446\u0432\u0435\u0442\u0430.", "", True, False))
                else:
                    results.append(ResolvedValue(name, "", "", "official_base_only" if official else "needs_review", reason, "", False, False))
                continue
            official_exact = [f for f in exact if f["source_key"] in OFFICIAL]
            if official_exact:
                chosen = official_exact[0]
                if _different(official):
                    results.append(ResolvedValue(name, "", "", "official_regions_conflict", "\u0420\u0430\u0437\u043d\u044b\u0435 \u0446\u0432\u0435\u0442\u0430 \u043e\u0444\u0438\u0446\u0438\u0430\u043b\u044c\u043d\u044b\u0445 \u0441\u0442\u0440\u0430\u043d\u0438\u0446 \u0442\u0440\u0435\u0431\u0443\u044e\u0442 \u043f\u0440\u043e\u0432\u0435\u0440\u043a\u0438.", "", True, False))
                elif any(_signature(f) != _signature(chosen) for f in exact if f["source_key"] not in OFFICIAL):
                    results.append(ResolvedValue(name, "", "", "needs_review", "\u0426\u0432\u0435\u0442 \u0442\u043e\u0447\u043d\u043e\u0433\u043e \u0430\u0440\u0442\u0438\u043a\u0443\u043b\u0430 \u0440\u0430\u0437\u043b\u0438\u0447\u0430\u0435\u0442\u0441\u044f \u0443 \u043e\u0444\u0438\u0446\u0438\u0430\u043b\u044c\u043d\u043e\u0433\u043e \u0441\u0430\u0439\u0442\u0430 \u0438 \u0434\u0438\u043b\u0435\u0440\u0430; \u043d\u0443\u0436\u043d\u0430 \u043f\u0440\u043e\u0432\u0435\u0440\u043a\u0430.", "", True, False))
                else:
                    results.append(ResolvedValue(name, chosen["normalized_value"], chosen["unit"], "full_sku_lg", "\u0426\u0432\u0435\u0442 \u0443\u043a\u0430\u0437\u0430\u043d \u043d\u0430 \u043e\u0444\u0438\u0446\u0438\u0430\u043b\u044c\u043d\u043e\u0439 \u0441\u0442\u0440\u0430\u043d\u0438\u0446\u0435 \u043f\u043e\u043b\u043d\u043e\u0433\u043e \u0430\u0440\u0442\u0438\u043a\u0443\u043b\u0430.", chosen["source_key"], False, True))
                continue
            for f in exact:
                if f["source_key"] == "dns" and f["source_key"] not in seen:
                    suppliers.append(f); seen.add(f["source_key"])
        exact_lg = [f for f in official if f["source_key"] in {"lg", "lg_kz", "lg_ru", "lg_global"} and pages.get(f["source_key"], {}).get("match_level") == "full_sku"]
        if exact_lg:
            if _different(official):
                names = " и ".join(sorted({o.get("site_name") or o["source_key"] for o in official}))
                results.append(ResolvedValue(name, "", "", "official_regions_conflict", f"Различие официальных источников: {names} дали разные значения.", "", True, False))
            elif suppliers and any(_signature(x) != _signature(exact_lg[0]) for x in suppliers):
                results.append(ResolvedValue(name, "", "", "needs_review", "Дилер и точная официальная страница LG дали разные значения; нужна проверка.", "", True, False))
            else:
                chosen = exact_lg[0]
                site_name = chosen.get("site_name") or chosen["source_key"]
                results.append(ResolvedValue(name, chosen["normalized_value"], chosen["unit"], "full_sku_lg", f"Значение на официальной странице полного артикула {site_name}.", chosen["source_key"], False, True))
            continue
        exact_lenovo = [f for f in official if f["source_key"] in {"lenovo_support","lenovo_psref"}
                        and pages.get(f["source_key"], {}).get("match_level") == "full_sku"
                        and not pages.get(f["source_key"], {}).get("error")]
        psref=[f for f in exact_lenovo if f['source_key']=='lenovo_psref']
        if psref:exact_lenovo=psref
        if exact_lenovo:
            if _different(exact_lenovo) or any(_signature(v) != _signature(exact_lenovo[0]) for v in suppliers):
                results.append(ResolvedValue(name, "", "", "needs_review", "Конфигурационные источники Lenovo расходятся.", "", True, False))
            else:
                chosen = exact_lenovo[0]
                results.append(ResolvedValue(name, chosen["normalized_value"], chosen["unit"],
                    "full_sku_official", "Факт точного MTM из официальной конфигурации Lenovo.", chosen['source_key'], False, True))
            continue
        exact_jbl = [f for f in official if f["source_key"] == "jbl" and pages.get("jbl", {}).get("match_level") in {"full_sku","model_confirmed"} and not pages.get("jbl", {}).get("error")]
        if exact_jbl:
            if _different(exact_jbl) or any(_signature(v) != _signature(exact_jbl[0]) for v in suppliers):
                results.append(ResolvedValue(name, "", "", "needs_review", "Точная официальная страница JBL и дилер дали разные значения.", "", True, False))
            else:
                chosen=exact_jbl[0]
                results.append(ResolvedValue(name, chosen["normalized_value"], chosen["unit"], "full_sku_official" if pages["jbl"]["match_level"]=="full_sku" else "model_confirmed_official", "Факт точной модели из официальной страницы JBL; цвет и комплект проверяются отдельно.", "jbl", False, pages["jbl"]["match_level"]=="full_sku"))
            continue
        exact_samsung = [f for f in official if f["source_key"] == "samsung"
                         and pages.get("samsung", {}).get("match_level") == "full_sku"
                         and not pages.get("samsung", {}).get("error")]
        if exact_samsung:
            if _different(exact_samsung):
                results.append(ResolvedValue(name, "", "", "needs_review",
                    "Разные значения на точной официальной странице Samsung требуют проверки.", "", True, False))
            else:
                chosen = exact_samsung[0]
                results.append(ResolvedValue(name, chosen["normalized_value"], chosen["unit"],
                    "full_sku_official", "Значение с точной официальной страницы товара Samsung.",
                    "samsung", False, True))
            continue
        if _different(suppliers):
            results.append(ResolvedValue(name,"","","needs_review","Несколько поставщиков подтверждают полный артикул, но значения расходятся.","",True,True)); continue
        if suppliers:
            chosen=suppliers[0]
            if len(suppliers)>=2:
                status="confirmed_two_suppliers"; source="+".join(sorted(f["source_key"] for f in suppliers)); reason="Совпадает у нескольких поставщиков полного артикула."
            else:
                status="confirmed_one_supplier"; source=chosen["source_key"]; reason=f"Полный артикул подтверждён одним поставщиком: {chosen.get('site_name') or chosen['source_key']}."
            if official and any(_signature(x)!=_signature(chosen) for x in official): reason += " Значение полного артикула имеет приоритет перед базовой моделью LG."
            results.append(ResolvedValue(name,chosen["normalized_value"],chosen["unit"],status,reason,source,False,True)); continue
        if official:
            if _different(official):
                names=" и ".join(sorted({o.get("site_name") or o["source_key"] for o in official}))
                results.append(ResolvedValue(name,"","","official_regions_conflict",f"Различие официальных источников: {names} дали разные значения.","",True,False))
            else:
                chosen=official[0]
                site_name=chosen.get("site_name") or chosen["source_key"]
                results.append(ResolvedValue(name,chosen["normalized_value"],chosen["unit"],"official_base_only",f"Найдено только у официального источника {site_name}; более точное совпадение (полный артикул/вариант) не подтверждено.",chosen["source_key"],False,False))
            continue
        if _different(values):
            results.append(ResolvedValue(name,"","","needs_review","Минимум два источника дали разные нормализованные значения.","",True,False))
        elif values:
            chosen=values[0]; results.append(ResolvedValue(name,chosen["normalized_value"],chosen["unit"],"needs_review","Значение найдено только в одном неподтверждённом источнике.",chosen["source_key"],False,False))
    return results
