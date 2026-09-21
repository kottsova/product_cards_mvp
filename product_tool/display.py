"""Russian presentation names and values for normalized product facts."""
from __future__ import annotations

import re
from typing import Iterable

DISPLAY_NAME_RU = {
    "pants_hanger_qty": "Количество вешалок для брюк",
    "drip_tray_qty": "Количество поддонов для сбора воды",
    "shelf_qty": "Количество полок",
    "package_weight": "Масса с упаковкой",
    "product_weight": "Масса товара",
    "package_dimensions": "Размеры упаковки",
    "product_dimensions": "Размеры продукта",
    "display_type": "Тип дисплея",
    "max_rpm": "Скорость подвижного крепления",
    "smart_diagnosis": "Функция Smart Diagnosis",
    "true_steam": "Технология TrueSteam",
    "capacity": "Вместимость",
    "color": "Цвет",
    "тип_управления": "Тип управления",
    "страна_производителя": "Страна производства",
    "количество_режимов_работы": "Количество режимов работы",
    "тип_компрессора": "Тип компрессора",
    "потребляемая_мощность": "Потребляемая мощность",
    "уровень_шума": "Уровень шума",
    "индикация": "Индикация",
    "дисплей": "Тип дисплея",
    "гарантия": "Гарантия",
    "комплектация": "Комплектация",
    "особенности": "Особенности",
    "энергопотребление": "Энергопотребление",
    "режим_гигиена": "Режим «Гигиена»",
    "режим_освежение": "Режим «Освежение»",
    "режим_сушка": "Режим «Сушка»",
    "максимальная_вместимость": "Максимальная вместимость",
    "вешалка_для_брюк": "Вешалка для брюк",
    "вешалка_для_рубашек": "Вешалка для рубашек",
}

SOURCE_NAMES = {
    "lg": "LG Казахстан", "lg_kz": "LG Казахстан", "lg_ru": "LG Россия",
    "sulpak": "Sulpak", "mechta": "Mechta", "manual": "Ручное решение",
    "sulpak+mechta": "Sulpak и Mechta",
}

STATUS_NAMES = {
    "official_base_only": "Найдено только у базовой модели LG",
    "official_regions_match": "Совпало в официальных регионах LG",
    "official_regions_conflict": "Различие официальных регионов",
    "confirmed_two_suppliers": "Подтверждено двумя поставщиками",
    "confirmed_one_supplier": "Подтверждено одним поставщиком",
    "matched": "Значения совпали",
    "needs_review": "Нужна проверка",
    "manual": "Выбрано вручную",
    "full_sku_lg": "Полный артикул найден на LG",
}


def display_name_ru(key: str, raw_names: Iterable[str] = ()) -> str:
    if key in DISPLAY_NAME_RU:
        return DISPLAY_NAME_RU[key]
    if re.search(r"[а-яё]", key, re.I):
        text = key.replace("_", " ").strip()
        return text[:1].upper() + text[1:]
    for raw in raw_names:
        if re.search(r"[а-яё]", raw, re.I):
            cleaned = " ".join(raw.split())
            return cleaned[:1].upper() + cleaned[1:]
    return "Дополнительная характеристика"


def display_source(key: str, site_name: str = "") -> str:
    return site_name or SOURCE_NAMES.get(key, key)


def display_status(status: str) -> str:
    return STATUS_NAMES.get(status, status.replace("_", " ").capitalize())


def display_value(value: str, unit: str = "") -> str:
    if value == "true" and unit == "bool":
        return "Да"
    if value == "false" and unit == "bool":
        return "Нет"
    dimensions = re.fullmatch(r"w=([^;]+);h=([^;]+);d=([^;]+)", value)
    if dimensions:
        return f"{dimensions.group(1)} × {dimensions.group(2)} × {dimensions.group(3)} мм (Ш × В × Г)"
    units = {"rpm": "об/мин", "kg": "кг", "mm": "мм", "bool": ""}
    shown_unit = units.get(unit, unit)
    return f"{value} {shown_unit}".strip()