"""LG customer-facing labels and dimensional projection.

Source facts and resolution decisions remain untouched. A dimension is split
only when the selected source explicitly gives the order of its three axes.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
import re
from typing import Any

from .normalization import _axis_order

RU_LABELS = {
    "how_to_cook": "\u041f\u043e\u0434\u0441\u043a\u0430\u0437\u043a\u0438 \u043f\u043e \u043f\u0440\u0438\u0433\u043e\u0442\u043e\u0432\u043b\u0435\u043d\u0438\u044e",
    "smartdiagnosis": "\u0424\u0443\u043d\u043a\u0446\u0438\u044f Smart Diagnosis",
    "add_30_seconds": "Добавление 30 секунд",
    "auto_cook": "Автоматическое приготовление",
    "auto_reheat": "Автоматический разогрев",
    "bake": "Выпечка",
    "air_fry": "Приготовление без масла",
    "completion_beeper": "Звуковой сигнал окончания работы",
    "control_type": "Тип управления",
    "control_display": "Дисплей управления",
    "control_location": "Расположение панели управления",
    "cavity_design": "Конструкция камеры",
    "cavity_light_type": "Тип освещения камеры",
    "child_lock": "Защита от детей",
    "convection_bake": "Выпечка с конвекцией",
    "country_of_origin": "Страна производства",
    "defrost": "Размораживание",
    "dehydrate": "Сушка продуктов",
    "door_color": "Цвет дверцы",
    "door_design": "Конструкция дверцы",
    "door_glass_design": "Стекло дверцы",
    "dust_bin_capacity_l_uncompressed__dimensions": "Объём пылесборника без сжатия",
    "easyclean": "Покрытие EasyClean",
    "exterior_design": "Внешний вид",
    "glass_tray_ea": "Стеклянный поддон",
    "grill": "Гриль",
    "installation_type": "Тип установки",
    "interior_color": "Цвет камеры",
    "inverter_defrost": "Инверторное размораживание",
    "kitchen_timer": "Кухонный таймер",
    "melt": "Растапливание",
    "memory_cook": "Память программ приготовления",
    "microwave_power_consumption_w": "Потребляемая мощность микроволн",
    "microwave_power_levels": "Уровни мощности микроволн",
    "microwave_power_output_w": "Выходная мощность микроволн",
    "outcase_color": "Цвет корпуса",
    "oven_capacity_l": "Объём камеры",
    "packing_dimensions_w_x_h_x_d_mm__dimensions": "Размеры упаковки",
    "power_output_w": "Выходная мощность",
    "printproof_finish": "Покрытие PrintProof",
    "product_dimensions_w_x_h_x_d_mm__dimensions": "Размеры товара",
    "product_weight_kg": "Вес товара",
    "proof": "Расстойка теста",
    "required_power_supply_volt_hz": "Электропитание",
    "roast": "Запекание",
    "rotate_ring_ea": "Роликовое кольцо",
    "rotate_shaft_ea": "Вал вращения",
    "sensor_cook": "Сенсорное приготовление",
    "sensor_reheat": "Сенсорный разогрев",
    "slow_cook": "Медленное приготовление",
    "soften": "Размягчение",
    "speed_convection": "Ускоренная конвекция",
    "speed_grill": "Ускоренный гриль",
    "stage_cooking": "Поэтапное приготовление",
    "steam_cook": "Приготовление на пару",
    "telescopic_pipe_material": "Материал телескопической трубы",
    "time_setting": "Настройка времени",
    "total_power_consumption_w": "Общая потребляемая мощность",
    "turntable_on_off": "Отключение поворотного стола",
    "turntable_size_mm": "Диаметр поворотного стола",
    "type": "Тип устройства",
    "warm": "Поддержание тепла",
    "bluetooth_surround_ready": "Поддержка Bluetooth Surround",
    "tv_sound_mode_share": "Передача звукового режима телевизора",
    "home_hub": "Центр умного дома",
    "optical": "Оптический вход",
    "product_weight__gross": "Вес брутто",
    "product_weight__net": "Вес нетто",
    "product_dimensions__depth": "Глубина товара",
    "product_dimensions__depth_door_open": "Глубина товара с открытой дверью",
    "product_dimensions__depth_with_door": "Глубина товара с дверью",
    "product_weight__without_stand": "Вес товара без подставки",
    "product_weight__with_stand": "Вес товара с подставкой",
    "product_dimensions__without_stand": "Размеры товара без подставки",
    "product_dimensions__with_stand": "Размеры товара с подставкой",
    "package_weight": "Вес с упаковкой",
    "product_weight": "Вес товара",
    "product_dimensions": "Размеры товара",
    "package_dimensions": "Размеры упаковки",
    "главный__dimensions": "Размеры основного блока",
    "главный__weight": "Вес основного блока",
    "сабвуфер__dimensions": "Размеры сабвуфера",
    "сабвуфер__weight": "Вес сабвуфера",
    "динамик__dimensions": "Размеры динамика",
    "картонная_коробка__dimensions": "Размеры картонной коробки",
    "основной_модуль_размер_ш_в_г_мм__dimensions": "Размеры основного модуля",
    "объем_пылесборника_л_со_сжатием__dimensions": "Объём пылесборника со сжатием",
    "user_manual_ea": "Инструкция в комплекте",
}
TECH_NAMES = {
    "ai_dd": "AI DD", "dolby_audio": "Dolby Audio", "dolby_digital": "Dolby Digital",
    "dts_digital_surround": "DTS Digital Surround", "filmmaker_mode": "FILMMAKER MODE",
    "google_cast": "Google Cast", "google_home_hub": "Google Home",
    "apple_airplay2": "Apple AirPlay 2", "apple_home": "Apple Home",
    "dj_loop": "DJ Loop", "dj_pad": "DJ PAD", "dj_scratcher": "DJ Scratcher",
    "multi_juke_box": "Multi Juke Box", "nfc_tag_on": "NFC Tag On",
    "smart_inverter": "Smart Inverter", "smart_pairing": "Smart Pairing",
    "thinq_wi_fi": "ThinQ (Wi-Fi)", "wireless_party_link_dual_mode": "Wireless Party Link (двойной режим)",
    "wireless_party_link_multi_mode": "Wireless Party Link (групповой режим)",
    "wow_interface": "WOW Interface", "voice_id": "Voice ID",
    "linear_cooling": "LINEAR Cooling", "doorcooling_plus": "DoorCooling+",
    "hygiene_fresh_plus": "Hygiene Fresh+", "hygienefresh_plus": "Hygiene Fresh+",
    "loadsense": "LoadSense", "ezdispense": "ezDispense",
    "coldwash": "ColdWash", "centum_system": "Centum System",
    "auto_dj": "Auto DJ", "sampler_creator": "Sampler Creator",
    "inverter_defrost": "Инверторное размораживание",
}
JUNK_KEYS = {"bar_code", "brand", "user_manual_ea"}
JUNK_PREFIXES = ("container_q_ty_",)
EMPTY_VALUES = {"n/a", "na", "not applicable", "не применимо", "unknown", "-", "—"}
DIMENSION_AXES = {"w": "Ширина", "h": "Высота", "d": "Глубина"}
PHYSICAL_RE = re.compile(r"(?:dimensions|weight|размер|габарит|ширин|высот|глубин|вес|масса)", re.I)
TECH_RE = re.compile(r"(?:LG|AI|Wi-Fi|Bluetooth|USB|HDMI|OLED|NANO|ThinQ|TurboWash|TrueSteam|Smart|Dolby|DTS|DJ|MP3|AAC|JPEG|MPEG|DVD|CD|HDR|ALLM|VRR|VESA|SPDIF|Simplink|EcoHybrid|LoadSense|ezDispense|WOW|NFC|DAB|LINEAR|DoorCooling|HygieneFresh|FILMMAKER)", re.I)


def classify(row: dict[str, Any]) -> str:
    key = row["normalized_name"]
    if key in JUNK_KEYS or key.startswith(JUNK_PREFIXES):
        return "logistics/internal metadata" if key != "user_manual_ea" else "marketing/support"
    value = row.get("resolved") or {}
    if (value.get("selected_value") or "").strip().casefold() in EMPTY_VALUES:
        return "logistics/internal metadata"
    sources = row.get("sources") or {}
    if sources and all(str(fact.get("raw_value") or "").strip().casefold() in EMPTY_VALUES for fact in sources.values()):
        return "logistics/internal metadata"
    return "product attribute"


def _clean_ru(raw: str, key: str) -> str:
    text = " ".join(raw.split())
    text = re.sub(r"\s*\(\s*\*?\s*AI\s*[-–—]\s*искусственный интеллект\s*\)", "", text, flags=re.I)
    text = re.sub(r"(?i)^AI\s+(?=.+\bAI\b)", "", text)
    text = re.sub(r"(?i)\s+AI\s+искусственный интеллект\b", " (ИИ)", text)
    text = re.sub(r"(?i)\bplus\b", "+", text)
    text = re.sub(r"(?i)\blg\b", "LG", text)
    text = re.sub(r"(?i)\bai\b", "AI", text)
    text = re.sub(r"(?i)\bwi[ -]?fi\b", "Wi-Fi", text)
    text = re.sub(r"(?i)\bbluetooth\b", "Bluetooth", text)
    text = re.sub(r"(?i)\b(hdmi|usb|hdr|allm|vrr|vesa|spdif|rf|fm|dj|dvd|dab|sbc|aac)\b", lambda m:m.group(1).upper(), text)
    text = re.sub(r"\s*\((?:body|gross|net|depth(?: door open| with door)?|without stand|with stand|washing|drying|dimensions|weight)\)\s*$", "", text, flags=re.I)
    text = re.sub(r"\s{2,}", " ", text).strip()
    scope = key.split("__", 1)[1] if "__" in key else ""
    if scope in {"washing", "drying"}:
        scope_ru = "стирка" if scope == "washing" else "сушка"
        if (("\u0441\u0442\u0438\u0440\u043a" if scope == "washing" else "\u0441\u0443\u0448\u043a") not in text.casefold()):
            text += f" ({scope_ru})"
    if scope == "body" and "корпус" not in text.casefold():
        text += " корпуса"
    return text[:1].upper() + text[1:] if text else ""


def canonical_label(row: dict[str, Any], *, exact_ru: bool = False) -> str:
    key = row["normalized_name"]
    if key in {"bluetooth", "wi_fi", "usb"}:
        return {"bluetooth": "Bluetooth", "wi_fi": "Wi-Fi", "usb": "USB"}[key]
    facts = row.get("sources") or {}
    names = " ".join(str(f.get("raw_name") or "") for f in facts.values()).casefold()
    physical = (key in {"product_weight", "package_weight", "product_dimensions",
                        "package_dimensions", "product_weight_kg"} or
                key.endswith(("__dimensions", "__weight")))
    if physical and key in RU_LABELS and "\u0442\u0432\u0438\u0442\u0435\u0440" not in names:
        return RU_LABELS[key]
    if exact_ru:
        ru = facts.get("lg_ru")
        if ru and re.search(r"[А-Яа-яЁё]", ru.get("raw_name") or ""):
            return _clean_ru(ru["raw_name"], key)
    for source in ("lg_ru", "lg_kz", "lg_global", "lg"):
        fact = facts.get(source)
        if fact and re.search(r"[А-Яа-яЁё]", fact.get("raw_name") or ""):
            return _clean_ru(fact["raw_name"], key)
    base, _, scope = key.partition("__")
    if key in RU_LABELS:
        label = RU_LABELS[key]
    elif base in TECH_NAMES:
        label = TECH_NAMES[base]
    elif key in TECH_NAMES:
        label = TECH_NAMES[key]
    elif base in RU_LABELS:
        label = RU_LABELS[base]
    else:
        raw = next((fact.get("raw_name") or "" for fact in facts.values()), "")
        if re.search(r"[А-Яа-яЁё]", raw):
            label = _clean_ru(raw, key)
        elif TECH_RE.search(raw):
            label = raw
        else:
            label = row.get("display_name") or raw or key
        label = re.sub(r"(?i)\s*\(dimensions\)|\s+dimensions\b", "", label)
    if scope in {"washing", "drying"} and not (("\u0441\u0442\u0438\u0440\u043a" if scope == "washing" else "\u0441\u0443\u0448\u043a") in label.casefold()):
        label += " (стирка)" if scope == "washing" else " (сушка)"
    return _clean_ru(label, key)


def _dimension_context(row: dict[str, Any]) -> tuple[str, str] | None:
    key = row["normalized_name"]
    raw = " ".join(str(fact.get("raw_name") or "") for fact in row.get("sources", {}).values()).casefold()
    if key.startswith("package_dimensions") or key.startswith("packing_dimensions") or "упаков" in raw or "packing" in raw:
        return "package", "упаковки"
    if key.startswith("product_dimensions") or key.startswith("основной_модуль_") or key in {"главный__dimensions", "сабвуфер__dimensions"}:
        if "твитер" in raw or "turntable" in raw:
            return None
        if "без подстав" in raw or "without_stand" in key:
            return "product_without_stand", "товара без подставки"
        if "с подстав" in raw or "with_stand" in key:
            return "product_with_stand", "товара с подставкой"
        if "основной модул" in raw or "main_unit" in key:
            return "main_unit", "основного модуля"
        if key == "главный__dimensions":
            return "main_unit", "основного блока"
        if key == "сабвуфер__dimensions":
            return "subwoofer", "сабвуфера"
        return "product", "товара"
    return None


def _proven_order(name: str) -> list[str]:
    direct = _axis_order(name)
    if direct:
        return direct
    text = name.casefold().replace("\u0445", "x").replace("?", "x")
    match = re.search(r"([\u0448\u0432\u0433whd])\s*x\s*([\u0448\u0432\u0433whd])\s*x\s*([\u0448\u0432\u0433whd])", text)
    mapping = {"\u0448": "w", "w": "w", "\u0432": "h", "h": "h", "\u0433": "d", "d": "d"}
    if match:
        order = [mapping[part] for part in match.groups()]
        if len(set(order)) == 3:
            return order
    return []


def normalize_measure(row: dict[str, Any]) -> dict[str, Any]:
    key = row["normalized_name"]
    resolved = row.get("resolved") or {}
    value = str(resolved.get("selected_value") or "")
    if not re.fullmatch(r"\d+(?:[.,]\d+)?", value) or resolved.get("conflict"):
        return row
    facts = row.get("sources") or {}
    chosen = facts.get(resolved.get("selected_source") or "")
    if not chosen:
        return row
    raw_name = str(chosen.get("raw_name") or "")
    unit = None
    if key == "product_weight_kg" and re.search(r"\(kg\)", raw_name, re.I):
        unit = "kg"
    elif key.startswith("product_dimensions__") and re.search(r"\b(?:mm|\u043c\u043c)\b", raw_name, re.I):
        unit = "mm"
    elif key.endswith("_w") and re.search(r"\(W\)", raw_name):
        unit = "W"
    elif key.endswith("_l") and re.search(r"\(L\)", raw_name):
        unit = "l"
    elif key.endswith("_mm") and re.search(r"\(mm\)", raw_name, re.I):
        unit = "mm"
    if not unit or resolved.get("selected_unit") not in {"", unit}:
        return row
    shown = {"kg": "\u043a\u0433", "mm": "\u043c\u043c", "W": "\u0412\u0442", "l": "\u043b"}[unit]
    row = dict(row)
    row["resolved"] = {**resolved, "selected_unit": unit, "display_value": f"{value} {shown}"}
    row["sources"] = {source: ({**fact, "display_value": f"{fact['normalized_value']} {shown}"}
                               if re.fullmatch(r"\d+(?:[.,]\d+)?", str(fact.get("normalized_value") or ""))
                               else fact) for source, fact in facts.items()}
    return row


def split_dimensions(row: dict[str, Any]) -> list[dict[str, Any]] | None:
    context = _dimension_context(row)
    selected = row.get("resolved") or {}
    if not context or selected.get("conflict") or not selected.get("selected_value"):
        return None
    facts = row.get("sources") or {}
    selected_fact = facts.get(selected.get("selected_source") or "")
    if not selected_fact:
        return None
    # Every displayed official source must identify the same axes independently.
    parsed: dict[str, dict[str, str]] = {}
    for source, fact in facts.items():
        name = fact.get("raw_name") or ""
        order = _proven_order(name) or _proven_order(fact.get("section") or "")
        if len(order) != 3:
            return None
        raw = str(fact.get("raw_value") or "")
        values = re.findall(r"\d+(?:[.,]\d+)?", raw)
        if len(values) != 3:
            return None
        unit_match = re.search(r"(?<![A-Za-zА-Яа-я])(мм|mm|см|cm|м)(?![A-Za-zА-Яа-я])", name + " " + raw, re.I)
        if not unit_match:
            # LG sometimes writes the axis and unit together: W x H x Dmm / \u0428x\u0412x\u0413\u043c\u043c.
            unit_match = re.search(r"(?:\u0413|[Dd])\s*(\u043c\u043c|mm)\b", name, re.I)
        if not unit_match:
            unit_match = re.search(r"(?<![A-Za-z\u0410-\u042f\u0430-\u044f])(\u043c\u043c|mm|\u0441\u043c|cm|\u043c)(?![A-Za-z\u0410-\u042f\u0430-\u044f])", str(fact.get("section") or ""), re.I)
        if not unit_match:
            return None
        unit = unit_match.group(1).casefold()
        multiplier = Decimal("10") if unit in {"см", "cm"} else Decimal("1000") if unit == "м" else Decimal("1")
        try:
            parsed[source] = {axis:format((Decimal(number.replace(",", "."))*multiplier).normalize(),"f") for axis,number in zip(order,values)}
        except InvalidOperation:
            return None
    chosen = parsed[selected.get("selected_source")]
    # The existing resolved fact must agree with the explicitly parsed axes.
    normalized = selected.get("selected_value") or ""
    canonical = re.fullmatch(r"w=([^;]+);h=([^;]+);d=([^;]+)", normalized)
    if canonical and any(canonical.group(i+1) != chosen[a] for i,a in enumerate(("w","h","d"))):
        return None
    scope, noun = context
    result = []
    for axis in ("w", "h", "d"):
        value = chosen[axis]
        derived = dict(row)
        derived["normalized_name"] = f"{scope}_{axis}_mm"
        derived["display_name"] = f"{DIMENSION_AXES[axis]} {noun}, мм"
        derived["section_name"] = "Габариты и вес"
        derived["derived_from"] = row["normalized_name"]
        derived["sources"] = {
            source: {**fact, "normalized_value": axes[axis], "unit": "mm",
                     "display_value": f"{axes[axis]} мм"}
            for source,fact in facts.items() for axes in [parsed[source]]
        }
        derived["resolved"] = {**selected, "selected_value": value, "selected_unit": "mm",
                               "display_value": f"{value} мм"}
        result.append(derived)
    return result



def safe_composite_dimensions(row: dict[str, Any]) -> dict[str, Any]:
    """Remove a defaulted mm label when no source actually states a unit."""
    if not _dimension_context(row):
        return row
    selected = row.get("resolved") or {}
    if selected.get("conflict") or selected.get("selected_unit") != "mm":
        return row
    facts = row.get("sources") or {}
    if not facts:
        return row
    explicit = re.compile(r"(?<![A-Za-z\u0410-\u042f\u0430-\u044f])(?:mm|\u043c\u043c|cm|\u0441\u043c|\u043c)(?![A-Za-z\u0410-\u042f\u0430-\u044f])|(?:\u0413|[Dd])\s*(?:mm|\u043c\u043c)\b", re.I)
    if all(explicit.search(" ".join(str(fact.get(field) or "") for field in ("raw_name", "raw_value", "section")))
           for fact in facts.values()):
        return row
    chosen = facts.get(selected.get("selected_source") or "")
    if not chosen:
        return row
    row = dict(row)
    row["resolved"] = {**selected, "display_value": chosen.get("raw_value") or selected.get("display_value", ""),
                       "selected_unit": ""}
    row["sources"] = {source: {**fact, "display_value": fact.get("raw_value") or fact.get("display_value", "")}
                      if not explicit.search(" ".join(str(fact.get(field) or "")
                                                  for field in ("raw_name", "raw_value", "section")))
                      else fact for source, fact in facts.items()}
    return row



SECTION_RU = {
    "Accessories": "\u041a\u043e\u043c\u043f\u043b\u0435\u043a\u0442\u0430\u0446\u0438\u044f",
    "Basic spec": "\u041e\u0441\u043d\u043e\u0432\u043d\u044b\u0435 \u0445\u0430\u0440\u0430\u043a\u0442\u0435\u0440\u0438\u0441\u0442\u0438\u043a\u0438",
    "Control features": "\u0423\u043f\u0440\u0430\u0432\u043b\u0435\u043d\u0438\u0435",
    "Convenience features": "\u0424\u0443\u043d\u043a\u0446\u0438\u0438 \u0443\u0434\u043e\u0431\u0441\u0442\u0432\u0430",
    "Cooking modes": "\u0420\u0435\u0436\u0438\u043c\u044b \u043f\u0440\u0438\u0433\u043e\u0442\u043e\u0432\u043b\u0435\u043d\u0438\u044f",
    "Design / finish": "\u0414\u0438\u0437\u0430\u0439\u043d \u0438 \u043f\u043e\u043a\u0440\u044b\u0442\u0438\u0435",
    "Microwave oven features": "\u0424\u0443\u043d\u043a\u0446\u0438\u0438 \u043c\u0438\u043a\u0440\u043e\u0432\u043e\u043b\u043d\u043e\u0432\u043e\u0439 \u043f\u0435\u0447\u0438",
    "Power / ratings": "\u041c\u043e\u0449\u043d\u043e\u0441\u0442\u044c \u0438 \u044d\u043d\u0435\u0440\u0433\u043e\u043f\u043e\u0442\u0440\u0435\u0431\u043b\u0435\u043d\u0438\u0435",
    "SMART TECHNOLOGY": "\u0423\u043c\u043d\u044b\u0435 \u0444\u0443\u043d\u043a\u0446\u0438\u0438",
    "SMART TV": "\u0423\u043c\u043d\u044b\u0435 \u0444\u0443\u043d\u043a\u0446\u0438\u0438",
    "DJ \u044d\u0444\u0444\u0435\u043a\u0442\u044b": "DJ-\u044d\u0444\u0444\u0435\u043a\u0442\u044b",
}


def canonical_section(section: str) -> str:
    return {key.casefold(): value for key, value in SECTION_RU.items()}.get(section.strip().casefold(), section.strip())

def dimensions_group(row: dict[str, Any]) -> bool:
    key = row["normalized_name"]
    if "\u0440\u0430\u0437\u0440\u0435\u0448\u0435\u043d\u0438\u0435" in key or "resolution" in key:
        return False
    if key.startswith(("dust_bin_capacity", "\u043e\u0431\u044a\u0435\u043c_", "\u043e\u0431\u044a\u0451\u043c_")):
        return False
    return bool(PHYSICAL_RE.search(key) or key.endswith(("_w_mm", "_h_mm", "_d_mm")))
