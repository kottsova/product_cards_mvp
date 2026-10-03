"""Russian labels for Bosch's English and German official specification trees.

These are label translations, not evidence or model-identity rules. Unmapped
technology names retain their original spelling and every raw label remains in
extracted_attribute_facts.
"""
from __future__ import annotations

import re
from . import lg_presentation

LABELS = {
    # Shared physical and electrical labels.
    "abmessungen des gerätes (h x b x t)": "Размеры товара (В × Ш × Г)",
    "abmessungen des verpackten gerätes": "Размеры упаковки",
    "dimensions": "Размеры товара",
    "net weight": "Вес товара",
    "main colour of product": "Цвет товара",
    "farbe": "Цвет товара",
    "gerätebreite": "Ширина товара",
    "anschlusswert": "Потребляемая мощность",
    "länge anschlusskabel": "Длина шнура питания",
    "length electrical supply cord": "Длина шнура питания",
    "maximum power": "Максимальная мощность",
    "noise level": "Уровень шума",
    "capacity": "Вместимость",
    "material body": "Материал корпуса",
    "water consumption": "Расход воды",
    "depth with open door 90 degree": "Глубина с дверью, открытой на 90°",
    # Cooktops.
    "ankochautomatik": "Автоматика закипания",
    "anti-anbrenn-sensor": "Датчик защиты от пригорания",
    "anzahl der elektr. warmhaltezonen": "Количество зон подогрева",
    "anzahl der kochzonen": "Количество зон нагрева",
    "anzahl der kontrollleuchten": "Количество индикаторов",
    "anzahl der leistungsstufen": "Количество уровней мощности",
    "art der kochzonen": "Тип зон нагрева",
    "art des timers": "Тип таймера",
    "auswahl der richtigen einstellung mit kochfeldassistent": "Подбор настроек помощником варочной панели",
    "automatische übernahme der einstellungen": "Автоматический перенос настроек",
    "automatische haubensteuerung": "Автоматическое управление вытяжкой",
    "automatische zonenauswahl": "Автоматический выбор зоны нагрева",
    "automatisches vereinen und trennen der kochzonen": "Автоматическое объединение зон нагрева",
    "bedienung": "Управление",
    "beleuchtetes kochfeld / zone light": "Подсветка зоны нагрева",
    "besonders kratzresistent dank glassprotect": "Покрытие GlassProtect",
    "display für energieverbrauch": "Индикация энергопотребления",
    "einbaudesign": "Дизайн встраивания",
    "erhöhen/verringern der leistung über pot move": "Регулировка мощности Pot Move",
    "favoriten-taste": "Кнопка избранного",
    "größe der kochzonen": "Размеры зон нагрева",
    "haubensteuerung via kochfeld": "Управление вытяжкой с варочной панели",
    "hauptoberflächenmaterial": "Материал поверхности",
    "heizungen mit booster": "Зоны с функцией Booster",
    "kochfeldart": "Тип варочной панели",
    "leistung der kochzonen": "Мощность зон нагрева",
    "minimale höhe der arbeitsplatte": "Минимальная толщина столешницы",
    "neustart": "Перезапуск",
    "nischenmaße für installation mm (hxbxt)": "Размеры ниши для установки (В × Ш × Г)",
    "quick start": "Быстрый старт",
    "quick switch-off": "Быстрое выключение",
    "restwärmeanzeige": "Индикатор остаточного тепла",
    "sicherheitsvorrichtungen": "Защитные функции",
    "smart home trigger für individuelle konfigurationen": "Сценарии Smart Home",
    "steckerart": "Тип вилки",
    "vernetzte hausgeräte mit home connect": "Поддержка Home Connect",
    "warmhaltestufe": "Режим поддержания тепла",
    # Dishwashers.
    "3rd rack": "Третья корзина",
    "additional operational options": "Дополнительные функции",
    "adjustable upper basket": "Регулировка верхней корзины",
    "anti-slip protection in the upper basket": "Защита от скольжения в верхней корзине",
    "basket system": "Система корзин",
    "built-in / free-standing": "Тип установки",
    "child saftety devices": "Защита от детей",
    "color / material panel": "Цвет и материал панели",
    "connected appliances with home connect": "Поддержка Home Connect",
    "cutlery system": "Размещение столовых приборов",
    "detergent detection": "Распознавание моющего средства",
    "display options": "Индикация",
    "drying system": "Система сушки",
    "extremely quiet and powerful brushless bldc motor": "Бесщёточный двигатель BLDC",
    "glass holder in the lower basket": "Держатель бокалов в нижней корзине",
    "height of removable worktop": "Высота съёмной столешницы",
    "home connect features": "Функции Home Connect",
    "installation typology": "Тип установки",
    "list of programmes": "Программы",
    "maximum number of place settings": "Вместимость, комплектов посуды",
    "number of cup racks in the lower basket": "Подставки для чашек в нижней корзине",
    "number of cup racks in the upper basket": "Подставки для чашек в верхней корзине",
    "number of flip tines in lower rack": "Складные держатели в нижней корзине",
    "number of flip tines in upper rack": "Складные держатели в верхней корзине",
    "precise glass protection": "Защита стекла",
    "program status light": "Индикатор выполнения программы",
    "removable top": "Съёмная верхняя панель",
    "variable hinge for special installation situations": "Регулируемая петля",
    "water management system": "Система управления водой",
    "water protection with warranty - aquastop": "Защита от протечек AquaStop",
    # Small kitchen appliances.
    "blade design": "Конструкция ножа",
    "blade removal": "Снятие ножа",
    "cleaning type": "Способ очистки",
    "gentle startup present": "Плавный запуск",
    "ice proof mixing beaker": "Кувшин для измельчения льда",
    "included accessories": "Аксессуары в комплекте",
    "material of the mixing beaker": "Материал кувшина",
    "max. rotation speed": "Максимальная скорость вращения",
    "number of automatic programmes": "Количество автоматических программ",
    "number of speed settings": "Количество скоростей",
    "pulse function": "Импульсный режим",
    "recipe book": "Книга рецептов",
    "safety device": "Защитное устройство",
}

LABELS.update({
    "led light with freezer light": "LED-освещение морозильной камеры",
    "list of warnings": "Предупреждения",
    "type of display": "Тип дисплея",
    "condensation efficiency (eu 2017/1369)": "Эффективность конденсации (ЕС 2017/1369)",
    "condensation efficiency class (eu 2017/1369)": "Класс эффективности конденсации (ЕС 2017/1369)",
    "repairability class": "Класс ремонтопригодности",
})

LABELS = {key.casefold(): value for key, value in LABELS.items()}

SECTIONS = {
    "общая информация": "Основные характеристики",
    "general": "Основные характеристики",
    "bauart": "Основные характеристики",
    "размер и вес": "Габариты и вес",
    "size and weight": "Габариты и вес",
    "installation": "Установка",
    "basket and cutlery system": "Корзины и столовые приборы",
    "cleaning technology and sensoric": "Мойка и датчики",
    "comfort": "Комфорт использования",
    "komfort": "Комфорт использования",
    "performance": "Производительность",
    "connectivity": "Подключение",
    "vernetzung": "Подключение",
    "safety": "Безопасность",
    "sicherheit": "Безопасность",
    "flexibilität der kochzonen": "Зоны нагрева",
    "kochassistent": "Помощник приготовления",
    "zeitsparend und effizient": "Быстрое приготовление",
}


def label(row: dict) -> str:
    raw = next((str(f.get("raw_name") or "") for f in (row.get("sources") or {}).values()), "")
    translated = LABELS.get(raw.casefold().strip())
    if translated:
        return translated
    if re.search(r"[а-яё]", raw, re.I):
        return row.get("display_name") or raw
    return row.get("display_name") or raw or row["normalized_name"]


def section(value: str) -> str:
    return SECTIONS.get(value.casefold().strip(), value)


def project(rows: list[dict]) -> list[dict]:
    result = []
    for original in rows:
        row = {**original, "display_name": label(original), "bosch_presentation": True}
        split = lg_presentation.split_dimensions(row)
        result.extend(split if split else [lg_presentation.safe_composite_dimensions(row)])
    return sorted(result, key=lambda row: row["display_name"].casefold())



def document_verified(document: dict, evidence: dict | None, pages: list[dict]) -> bool:
    """A typed PDF is checked only when bytes and its exact PDP link were checked."""
    exact = any(page.get("source_key") == "bosch_home" and page.get("match_level") == "full_sku"
                and not page.get("error") and page.get("url") == document.get("relation_url")
                for page in pages)
    checks = (evidence or {}).get("pdf_checks") or []
    legacy = bool((evidence or {}).get("manual_verified_sha256") and
                  (evidence or {}).get("manual_verified") and document.get("language") == "Русский")
    return exact and (legacy or any(check.get("url") == document.get("direct_url") and check.get("checked")
                                    for check in checks))
