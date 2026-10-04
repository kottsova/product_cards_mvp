"""Attribute fact normalization without losing source text."""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation
import re
from typing import Iterable

from .adapters.common import RawAttribute, clean_text


@dataclass(frozen=True)
class NormalizedFact:
    raw_name: str
    raw_value: str
    normalized_name: str
    normalized_value: str
    unit: str
    section: str = ""
    value_cell: bool | None = None


NAME_RULES = (
    (re.compile(r"^размеры?\s+нагревательных\s+элементов", re.I), "heating_element_sizes"),
    (re.compile(r"^abmessungen des verpackten gerätes$", re.I), "package_dimensions"),
    (re.compile(r"^abmessungen des gerätes", re.I), "product_dimensions"),
    (re.compile(r"^dimensions$", re.I), "product_dimensions"),
    (re.compile(r"^net weight$", re.I), "product_weight"),
    (re.compile(r"^(?:main colour of product|farbe)$", re.I), "color"),
    (re.compile(r"^(?:версия\s+bluetooth|bluetooth\s+version)$", re.I), "bluetooth_version"),
    (re.compile(r"drip\s*tray", re.I), "drip_tray_qty"),
    (re.compile(r"pants\s*hanger", re.I), "pants_hanger_qty"),
    (re.compile(r"shelf", re.I), "shelf_qty"),
    # Stage 21 (D3): a rule now applies only when the NAME BEGINS with the quantity word. Before, "цвет" anywhere folded "Цвета Бит",
    # "Цветовая Гамма", "Стабилизатор Черного Цвета" and "Цвет (подставка)" into one "color"; "загруз" folded "Детектор загрузки" and
    # "Максимальная загрузка при стирке" into "capacity"; "диспле" folded "ЖК-дисплей" and "Автовыключение дисплея" into "display_type";
    # "макс.*об" folded "Макс. время работы (обычный режим)" into "max_rpm". Those are other quantities: they keep their own names now.
    # A laundry "maximum load" is a load, and a shipping box / transport size is packaging: neither is the product weight or size.
    (re.compile(r"^макс\w*\.?\s*(?:вес|масса|загрузк\w*)|^(?:вес|масса)\s+белья|^загрузк\w*\s+белья", re.I), "max_load_weight"),
    (re.compile(r"^(?:вес|масса).*(?:ящик|короб|транспортир)", re.I), "package_weight"),
    (re.compile(r"^(?:размер|габарит)\w*.*(?:ящик|короб|транспортир)", re.I), "package_dimensions"),
    (re.compile(r"^(?:вес|масса).*без\s+упаков", re.I), "product_weight"),
    (re.compile(r"^(?:вес|масса).*(?:в|с)\s+укаковк", re.I), "package_weight"),
    (re.compile(r"^(?:вес|масса).*упаков", re.I), "package_weight"),
    (re.compile(r"^(?:вес|масса)", re.I), "product_weight"),
    (re.compile(r"^(?:размер|габарит)\w*.*упаков", re.I), "package_dimensions"),
    (re.compile(r"^(?:размер\w*\s+)?диагонал", re.I), "screen_diagonal"),
    # Stage 26 (Samsung pages): a display's size and an "image size" mode are not the size of the product.
    (re.compile(r"^размер\s+изображения", re.I), "image_size_mode"),
    (re.compile(r"^размер\w*\s*(?:экрана|дисплея)|^размер\w*\s*\((?:основной\s+|внешний\s+|дополнительный\s+)?(?:экран|дисплей)", re.I), "display_size"),
    (re.compile(r"^(?:размер|габарит|ширин|высот|глубин)(?!\w*\s+цвет)", re.I), "product_dimensions"),
    # Stage 27 (a Samsung dishwasher page): "Цвет/материал: Нет" is a yes/no option and "Цвет подсветки дисплея" is the colour of a backlight, not the product colour.
    (re.compile(r"^цвет\s*/\s*материал", re.I), "color_material_option"),
    (re.compile(r"^цвет\w*\s+подсветк", re.I), "backlight_color"),
    (re.compile(r"^цвет(?![а-я])", re.I), "color"),
    (re.compile(r"^(?:тип\s+)?дисплей(?![\w-])|^(?:тип\s+)?дисплея(?![\w-])", re.I), "display_type"),
    (re.compile(r"true\s*steam", re.I), "true_steam"),
    (re.compile(r"умн.*диагност", re.I), "smart_diagnosis"),
    (re.compile(r"оборот|об/мин|скорост.*колебан", re.I), "max_rpm"),
    (re.compile(r"^загрузк", re.I), "capacity"),
)

AXIS_MAP = {
    "ш": "w", "w": "w", "width": "w", "ширина": "w",
    "в": "h", "h": "h", "height": "h", "высота": "h",
    "г": "d", "d": "d", "depth": "d", "глубина": "d",
    "b": "w", "t": "d",  # German Breite/Tiefe in explicit H x B x T labels.

}
TRUE_VALUES = {"да", "есть", "yes", "true", "имеется", "ja"}
FALSE_VALUES = {"нет", "no", "false", "отсутствует", "nein"}
_PRESENT_MARKERS = frozenset({"●", "•", "O", "+"})
_AMBIGUOUS_MARKERS = frozenset({"○"})
_ABSENT_MARKERS = frozenset({"-", "–", "—", "−"})
_MARKED_VERSION = re.compile(r"^\s*([●•O+])\s*(?:v|ver(?:sion)?|версия)\s*(\d+(?:[.]\d+)*)\b", re.I)


# Stage 21 (D3). The rules above fold many names into one ("вес", "масса", "размер", "габарит", "цвет" ...). That is right when the
# names describe the SAME quantity in two regions, and wrong when one page states the quantity for different parts or states of
# the product (TV with and without stand, gross and net weight, indoor and outdoor unit, door and body colour): those are different
# physical quantities and must not be compared with each other. A closed vocabulary of such qualifiers is appended to the name;
# a qualifier that is not in the vocabulary is simply not recognised and the values keep sharing one name, so an unknown case
# still ends in a conflict for a person to look at, never in a silent merge. Two different values of the same quantity (same
# base name, same qualifier) still conflict.
_QUALIFIABLE = frozenset({"product_weight", "product_dimensions", "package_weight", "package_dimensions", "max_load_weight"})
_QUALIFIERS = (
    (re.compile(r"без\s+подставк"), "without_stand"),
    (re.compile(r"(?<![а-я])с\s+подставк"), "with_stand"),
    (re.compile(r"брутто"), "gross"),
    (re.compile(r"нетто"), "net"),
    (re.compile(r"внутренн\w*\s+блок"), "indoor_unit"),
    (re.compile(r"наружн\w*\s+блок"), "outdoor_unit"),
    (re.compile(r"внутренн\w*\s+(?:пространств|камер|объ)"), "cavity"),
    (re.compile(r"(?:поворотн|вращающ)\w*\s+стол"), "turntable"),
    (re.compile(r"сабвуфер"), "subwoofer"),
    (re.compile(r"основн\w*\s+(?:модул|издели)"), "main_unit"),
    # Stage 28 (a Samsung robot vacuum and its cleaning station): a size / weight row that names the station (or, by an explicit manual table, the main device) is that part's own quantity.
    (re.compile(r"станци[яи]\s+очистки"), "cleaning_station"),
    (re.compile(r"фронтальн"), "front_speaker"),
    (re.compile(r"тыл|задн\w*\s+колонк"), "rear_speaker"),
    (re.compile(r"центральн"), "center_speaker"),
    (re.compile(r"настенн\w*\s+крепл"), "wall_mount"),
    (re.compile(r"открыт\w*\s+двер"), "door_open"),
    (re.compile(r"с\s+учет\w*\s+двер"), "with_door"),
    # Stage 26 (Samsung refrigerators): depth/height stated with and without the door handle, without the doors, with and without the hinges, and for the packaging are different quantities.
    (re.compile(r"(?<![а-я])с\s+двер\w*\s+ручк"), "with_handle"),
    (re.compile(r"без\s+двер\w*\s+ручк"), "without_handle"),
    (re.compile(r"без\s+двер(?!\w*\s+ручк)"), "without_door"),
    (re.compile(r"с\s+учет\w*\s+петел"), "with_hinges"),
    (re.compile(r"без\s+учет\w*\s+петел"), "without_hinges"),
    (re.compile(r"стирк"), "washing"),
    (re.compile(r"сушк"), "drying"),
)
# The same screen diagonal in inches and in centimetres is stated twice; the unit word tells them apart.
_DIAGONAL_UNITS = ((re.compile(r"дюйм|\""), "inch"), (re.compile(r"\(см\)|см"), "cm"))
_COLOR_PARTS = (
    (re.compile(r"дверц|двери|дверь"), "door"),
    (re.compile(r"панел|panel"), "panel"),
    (re.compile(r"корпус"), "body"),
    (re.compile(r"внутри|внутренн"), "inside"),
    (re.compile(r"подставк"), "stand"),
)
_DIMENSION_VALUE = re.compile(r"^\s*\d+(?:[.,]\d+)?\s*[x×х]\s*\d+(?:[.,]\d+)?(?:\s*[x×х]\s*\d+(?:[.,]\d+)?)?\s*(?:mm|мм|cm|см|m|м)?\s*$", re.I)
_WEIGHT_VALUE = re.compile(r"^\s*\d+(?:[.,]\d+)?\s*(?:kg|кг|g|г)\s*$", re.I)


def _cleaned(name: str) -> str:
    return clean_text(name).casefold().replace("ё", "е")


def _mapped(cleaned: str) -> str:
    for pattern, canonical in NAME_RULES:
        if pattern.search(cleaned):
            return canonical
    return ""


def _base_name(name: str) -> str:
    cleaned = _cleaned(name)
    return _mapped(cleaned) or re.sub(r"[^a-zа-я0-9]+", "_", cleaned.replace("+", " plus ")).strip("_")


def _qualifier(cleaned: str, base: str) -> str:
    if base == "screen_diagonal":
        found = [label for pattern, label in _DIAGONAL_UNITS if pattern.search(cleaned)]
    elif base in _QUALIFIABLE:
        found = [label for pattern, label in _QUALIFIERS if pattern.search(cleaned)]
        axis = re.match(r"(ширин|высот|глубин)", cleaned) if base == "product_dimensions" else None
        if axis:  # Stage 22: one edge of the product (depth 455) is not the W x H x D triple, whatever the two are called
            found.append({"ширин": "width", "высот": "height", "глубин": "depth"}[axis.group(1)])
        if base == "product_dimensions" and re.search(r"упаков|короб", cleaned):  # Stage 26: "Глубина упаковки" is the packaging's edge (the names that already say package_* are unchanged)
            found.append("packaging")
    elif base == "color":
        found = [label for pattern, label in _COLOR_PARTS if pattern.search(cleaned)]
    else:
        found = []
    return "_".join(sorted(set(found)))


def _section_scope(section: str) -> str:
    """Only component-specific LG headings change the fact's identity."""
    title = _cleaned(section)
    if re.search(r"сушильн|программ\w*\s+сушк", title):
        return "drying"
    if re.search(r"стиральн|программ\w*\s+стирк", title):
        return "washing"
    return ""


def normalize_name(name: str, section: str = "") -> str:
    cleaned = _cleaned(name)
    base = _base_name(name)
    qualifier = _qualifier(cleaned, base)
    scope = _section_scope(section)
    parts = list(filter(None, (qualifier, scope)))
    return f"{base}__{'_'.join(dict.fromkeys(parts))}" if parts else base


def _decimal(value: str) -> Decimal | None:
    try:
        return Decimal(value.replace(",", "."))
    except InvalidOperation:
        return None


def _format_decimal(value: Decimal) -> str:
    return format(value.normalize(), "f")


def _axis_order(name: str) -> list[str]:
    content = clean_text(name).casefold().replace("×", "x").replace("х", "x")
    parenthesized = re.findall(r"\(([^)]*(?:x|/)[^)]*)\)", content)
    candidates = parenthesized or [content]
    for candidate in candidates:
        # Bosch and LG explicitly print axes as ШxВxГмм or HxBxT, sometimes
        # joining the unit to the last axis. Strip only that trailing unit.
        candidate = re.sub(r"[\s,]*(?:мм|mm)\s*$", "", candidate)
        split_tokens = [part.strip(" .,:;-") for part in re.split(r"[x/]", candidate)]
        mapped = [AXIS_MAP[token] for token in split_tokens if token in AXIS_MAP]
        if len(mapped) >= 3 and len(set(mapped[:3])) == 3:
            return mapped[:3]
        tokens = re.findall(r"(?:^|[^a-zа-я])([швгwhd])(?:[^a-zа-я]|$)", candidate)
        mapped = [AXIS_MAP[token] for token in tokens if token in AXIS_MAP]
        if len(mapped) >= 3 and len(set(mapped[:3])) == 3:
            return mapped[:3]
    return []


def _normalize_dimensions(name: str, value: str) -> tuple[str, str] | None:
    numbers = [_decimal(x) for x in re.findall(r"\d+(?:[.,]\d+)?", value)]
    numbers = [x for x in numbers if x is not None]
    if len(numbers) < 3:
        return None
    unit_match = re.search(r"(?<![а-яa-z])(мм|mm|см|cm|м)(?![а-яa-z])", value, re.I)
    unit = (unit_match.group(1).casefold() if unit_match else "мм")
    multiplier = Decimal("10") if unit in {"см", "cm"} else Decimal("1000") if unit == "м" else Decimal("1")
    values = [number * multiplier for number in numbers[:3]]
    order = _axis_order(name)
    if not order:
        # Keep an unordered triple as source text; axis values cannot be inferred.
        return None
    axes = dict(zip(order, values))
    canonical = ";".join(f"{axis}={_format_decimal(axes[axis])}" for axis in ("w", "h", "d"))
    return canonical, "mm"


def _normalize_weight(name: str, value: str) -> tuple[str, str] | None:
    match = re.search(r"(\d+(?:[.,]\d+)?)\s*(кг|kg|г|g)\b", value, re.I)
    if match:
        number = _decimal(match.group(1))
        unit = match.group(2).casefold()
    else:
        number_match = re.fullmatch(r"\s*(\d+(?:[.,]\d+)?)\s*", value)
        unit_match = re.search(r"(?:^|[^а-яa-z])(кг|kg|г|g)(?:[^а-яa-z]|$)", name, re.I)
        if not number_match or not unit_match:
            return None
        number = _decimal(number_match.group(1))
        unit = unit_match.group(1).casefold()
    if number is None:
        return None
    kilograms = number / Decimal("1000") if unit in {"г", "g"} else number
    return _format_decimal(kilograms), "kg"


def normalize_value(name: str, value: str, *, value_cell: bool | None = None) -> tuple[str, str]:
    cleaned = clean_text(value)
    folded = cleaned.casefold().replace("ё", "е")
    canonical_name = _base_name(name)  # value parsing follows the quantity, not its qualifier
    if value_cell is True:
        if not cleaned:
            return "unknown", "unknown"
        if cleaned in _PRESENT_MARKERS:
            return "true", "bool"
        if cleaned in _AMBIGUOUS_MARKERS:
            return "unknown", "unknown"
        if cleaned in _ABSENT_MARKERS:
            return "false", "bool"
        parts = [part.strip() for part in cleaned.split("/")]
        if len(parts) > 1 and all(part in _PRESENT_MARKERS | _ABSENT_MARKERS for part in parts):
            return "/".join("true" if part in _PRESENT_MARKERS else "false" for part in parts), "bool_vector"
        if _MARKED_VERSION.match(cleaned):
            return "true", "bool"
    if canonical_name.endswith("dimensions"):
        dimensions = _normalize_dimensions(name, cleaned)
        if dimensions:
            return dimensions
    if canonical_name.endswith("weight"):
        weight = _normalize_weight(name, cleaned)
        if weight:
            return weight
    if folded in {"опционно", "опционально"} or re.fullmatch(r"(?:o|●)\s*\(опционально\)", folded):
        return "optional", ""
    if re.match(r"^(?:да|yes)\s*\([^)]*\)$", folded):
        return "true", "bool"
    if canonical_name == "тип_компрессора" and re.search(r"(?:смарт|умн).*инвертор|инвертор.*(?:смарт|умн)", folded) and "bldc" in folded:
        return "smart inverter compressor (bldc)", ""
    # Legacy adapters do not record cell context yet; retain their prior
    # interpretation. LG's marked value cells above use exact tokens only.
    if value_cell is None and folded.startswith(("●", "•")):
        return "true", "bool"
    if folded in TRUE_VALUES or (value_cell is None and folded == "+"):
        return "true", "bool"
    if folded in FALSE_VALUES or (value_cell is None and folded == "-" and
                                  (canonical_name in {"true_steam", "smart_diagnosis"} or
                                   re.search(r"налич|функц|поддерж", name, re.I))):
        return "false", "bool"
    if canonical_name == "max_rpm":
        rpm = re.search(r"\d+(?:[.,]\d+)?", folded)
        if rpm:
            number = _decimal(rpm.group(0))
            if number is not None:
                return _format_decimal(number), "rpm"
    number_match = re.fullmatch(r"(\d+(?:[.,]\d+)?)\s*(об/мин|rpm|кг|kg|мм|mm|см|cm)?", folded)
    if number_match:
        number = _decimal(number_match.group(1))
        unit = number_match.group(2) or ""
        if number is not None:
            if unit in {"см", "cm"}:
                return _format_decimal(number * Decimal("10")), "mm"
            return _format_decimal(number), {"кг": "kg", "мм": "mm", "об/мин": "rpm"}.get(unit, unit)
    return re.sub(r"\s+", " ", folded.replace("×", "x") if re.search(r"\d\s*[xх×]\s*\d", folded) else folded).strip(), ""


def normalize_fact(fact: RawAttribute) -> NormalizedFact:
    name = normalize_name(fact.name, fact.section)
    value, unit = normalize_value(fact.name, fact.value, value_cell=fact.value_cell)
    if name == "тип__drying" and re.search(r"конденсац|конденсатора", _cleaned(fact.value)):
        value, unit = "condensing dryer", ""
    # A version and an availability marker in Bluetooth rows are different concepts.
    if _cleaned(fact.name) == "bluetooth" and re.fullmatch(r"(?:ver(?:sion)?\s*)?v?\s*\d+(?:[.]\d+)+", _cleaned(fact.value)):
        name = "bluetooth_version"
        value, unit = re.sub(r"[.]0$", "", re.search(r"\d+(?:[.]\d+)+", fact.value).group()), ""
    # The LG RU table uses a single letter O as a tick marker.
    if fact.value_cell is not False and fact.section and clean_text(fact.value).casefold() == "o":
        value, unit = "true", "bool"
    # A descriptive adjective repeated as the entire value confirms that feature.
    words = _cleaned(fact.name).split()
    if len(words) >= 2 and _cleaned(fact.value) == words[0] and words[0].endswith(("ая", "ый", "ое", "ие")):
        value, unit = "true", "bool"
    if not _mapped(_cleaned(fact.name)):
        # An unmapped name (a spec row named only by the part, e.g. "Главный" / "Сабвуфер") that carries a size in one row and a
        # weight in the next: the kind of the value says which quantity it is.
        raw = clean_text(fact.value)
        if _DIMENSION_VALUE.match(raw):
            name += "__dimensions"
        elif _WEIGHT_VALUE.match(raw):
            name += "__weight"
    return NormalizedFact(fact.name, fact.value, name, value, unit, fact.section, fact.value_cell)


_PLACEHOLDER = re.compile(r"^[-‐-―−]+$")


def normalize_facts(facts: Iterable[RawAttribute]) -> list[NormalizedFact]:
    result = []
    for fact in facts:
        if not clean_text(fact.name) or (not clean_text(fact.value) and fact.value_cell is not True):
            continue
        normalized = normalize_fact(fact)
        # An empty LG value cell is observed but unknown. Keep its raw row;
        # resolution ignores unknown rather than treating it as absence.
        if _PLACEHOLDER.match(clean_text(fact.value)) and normalized.unit != "bool" and fact.value_cell is not True:
            continue
        result.append(normalized)
        if fact.value_cell is True:
            version = _MARKED_VERSION.match(clean_text(fact.value))
            if version:
                name = normalized.normalized_name
                if name != "bluetooth_version" and not name.endswith("_version"):
                    result.append(NormalizedFact(
                        fact.name, fact.value, f"{name}_version",
                        re.sub(r"[.]0$", "", version.group(2)), "",
                        fact.section, fact.value_cell,
                    ))
    # A bare overview number and an explicitly unit-marked detail value can
    # describe the same measurement. Infer a unit only from the same canonical
    # field and identical numeric value on this very page; keep raw text intact.
    explicit: dict[tuple[str, str], set[str]] = {}
    for row in result:
        if row.unit:
            explicit.setdefault((row.normalized_name, row.normalized_value), set()).add(row.unit)
    for index, row in enumerate(result):
        units = explicit.get((row.normalized_name, row.normalized_value), set())
        if not row.unit and re.fullmatch(r"\d+(?:[.]\d+)?", row.normalized_value) and len(units) == 1:
            result[index] = replace(row, unit=next(iter(units)))
    return result
