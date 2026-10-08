"""Russian presentation names and values for normalized product facts."""
from __future__ import annotations

import re
from typing import Iterable

DISPLAY_NAME_RU = {
    "bluetooth": "Bluetooth",
    "bluetooth_version": "Версия Bluetooth",
    "версия_bluetooth": "Версия Bluetooth",
    "wi_fi": "Wi-Fi",
    "wi_fi_version": "Версия Wi-Fi",
    "версия_wi_fi": "Версия Wi-Fi",
    "usb": "USB",
    "usb_ports": "Порты USB",
    "usb_port_count": "Порты USB",
    "usb_порты": "Порты USB",
    "количество_портов_usb": "Порты USB",
    "количество_usb_портов": "Порты USB",
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
    "lg_global": "LG official other region",
    "sulpak": "Sulpak", "manual": "Ручное решение", "dns": "DNS", "bosch_home": "Bosch Home Казахстан", "samsung": "Samsung Казахстан",
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
    "full_sku_official": "\u041f\u043e\u043b\u043d\u044b\u0439 \u0430\u0440\u0442\u0438\u043a\u0443\u043b \u043d\u0430 \u043e\u0444\u0438\u0446\u0438\u0430\u043b\u044c\u043d\u043e\u0439 \u0441\u0442\u0440\u0430\u043d\u0438\u0446\u0435 Samsung",
    "full_sku_lg": "Полный артикул найден на LG",
}


def display_name_ru(key: str, raw_names: Iterable[str] = ()) -> str:
    if key in DISPLAY_NAME_RU:
        return DISPLAY_NAME_RU[key]
    if re.search(r"[а-яё]", key, re.I):
        text = key.replace("_", " ").strip()
        return text[:1].upper() + text[1:]
    for raw in raw_names:
        cleaned = " ".join(str(raw).split())
        if cleaned and re.search(r"[A-Za-zА-Яа-яЁё]", cleaned):
            label = cleaned[:1].upper() + cleaned[1:]
            if "__" in key:
                context = key.rsplit("__", 1)[1].replace("_", " ")
                context = {"drying": "сушка", "washing": "стирка"}.get(context, context)
                label += f" ({context})"
            return label
    # Source labels remain in raw evidence; a named Latin feature is a real label.
    text = key.replace("__", " (").replace("_", " ")
    if " (" in text:
        text += ")"
    return text[:1].upper() + text[1:] if text else "Дополнительная характеристика"



def display_source(key: str, site_name: str = "") -> str:
    return site_name or SOURCE_NAMES.get(key, key)


SAMSUNG_STATUS_NAMES = {"official_base_only": "Значение официального сайта Samsung; вариант оценивается отдельно"}


def display_status(status: str, source: str = "") -> str:
    if source.startswith('playstation'):
        return {'full_sku_official':'Параметр точного коммерческого артикула PlayStation','model_confirmed_official':'Общая характеристика модели PlayStation','hardware_confirmed_official':'Характеристика оборудования с подтверждённым CFI'}.get(status,STATUS_NAMES.get(status,status))
    if source == "apple_model" and status == "model_confirmed_official":
        return "Подтверждено для точной модели Apple"
    if source == "apple" and status == "full_sku_official":
        return "Параметр точного коммерческого артикула Apple"
    if source == "jbl" and status == "model_confirmed_official":
        return "Характеристика точной модели JBL; вариант проверяется отдельно"
    if source == "jbl" and status == "full_sku_official":
        return "Полный артикул на официальной странице JBL"
    if source == "samsung" and status in SAMSUNG_STATUS_NAMES:
        return SAMSUNG_STATUS_NAMES[status]
    return STATUS_NAMES.get(status, status.replace("_", " ").capitalize())


def display_value(value: str, unit: str = "") -> str:
    if value == "unknown" and unit == "unknown":
        return "Не указано"
    if unit == "bool_vector":
        return " / ".join("Да" if part == "true" else "Нет" for part in value.split("/"))
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

def display_access_error(message: str) -> str:
    """Distinguish a synthetic policy response from a site's actual HTTP status."""
    if "[policy_challenge_confirmed]" in message:
        return message.replace(
            "HTTP-ошибка: HTTP 403 [policy_challenge_confirmed]",
            "HTTP 200: страница проверки сайта; товарные данные не получены",
        )
    if "policy_host_stopped" not in message:
        return message
    source = message.split(":", 1)[0] if ":" in message else ""
    if source.casefold().startswith(("http", "policy_")):
        source = ""
    prefix = source + ": " if source else ""
    return prefix + "Внутренний access-stop: запрос к этой странице не отправлялся."
