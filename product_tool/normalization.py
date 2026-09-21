"""Attribute fact normalization without losing source text."""

from __future__ import annotations

from dataclasses import dataclass
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


NAME_RULES = (
    (re.compile(r"вес.*упаков|масса.*упаков", re.I), "package_weight"),
    (re.compile(r"вес|масса", re.I), "product_weight"),
    (re.compile(r"размер.*упаков|габарит.*упаков", re.I), "package_dimensions"),
    (re.compile(r"размер|габарит|ширин|высот|глубин", re.I), "product_dimensions"),
    (re.compile(r"цвет", re.I), "color"),
    (re.compile(r"(?:тип\\s+)?диспле", re.I), "display_type"),
    (re.compile(r"true\s*steam", re.I), "true_steam"),
    (re.compile(r"умн.*диагност", re.I), "smart_diagnosis"),
    (re.compile(r"макс.*об|оборот|скорост.*колебан", re.I), "max_rpm"),
    (re.compile(r"загруз", re.I), "capacity"),
)

AXIS_MAP = {
    "ш": "w", "w": "w", "width": "w", "ширина": "w",
    "в": "h", "h": "h", "height": "h", "высота": "h",
    "г": "d", "d": "d", "depth": "d", "глубина": "d",
}
TRUE_VALUES = {"да", "есть", "●", "•", "+", "yes", "true", "имеется"}
FALSE_VALUES = {"нет", "-", "no", "false", "отсутствует"}


def normalize_name(name: str) -> str:
    cleaned = clean_text(name).casefold().replace("ё", "е")
    for pattern, canonical in NAME_RULES:
        if pattern.search(cleaned):
            return canonical
    return re.sub(r"[^a-zа-я0-9]+", "_", cleaned).strip("_")


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
        # Common source default is W×H×D. Unknown order remains explicit.
        order = ["w", "h", "d"]
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


def normalize_value(name: str, value: str) -> tuple[str, str]:
    cleaned = clean_text(value)
    folded = cleaned.casefold().replace("ё", "е")
    canonical_name = normalize_name(name)
    if canonical_name.endswith("dimensions"):
        dimensions = _normalize_dimensions(name, cleaned)
        if dimensions:
            return dimensions
    if canonical_name.endswith("weight"):
        weight = _normalize_weight(name, cleaned)
        if weight:
            return weight
    if folded in TRUE_VALUES:
        return "true", "bool"
    if folded in FALSE_VALUES:
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
    return re.sub(r"\s+", " ", folded.replace("×", "x").replace("х", "x")).strip(), ""


def normalize_fact(fact: RawAttribute) -> NormalizedFact:
    name = normalize_name(fact.name)
    value, unit = normalize_value(fact.name, fact.value)
    return NormalizedFact(fact.name, fact.value, name, value, unit)


def normalize_facts(facts: Iterable[RawAttribute]) -> list[NormalizedFact]:
    return [normalize_fact(fact) for fact in facts if clean_text(fact.name) and clean_text(fact.value)]
