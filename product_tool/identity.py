"""Structured product identity and conservative identity verification.

The verifier intentionally consumes extracted fields, never arbitrary page HTML.
Missing evidence is different from conflicting evidence.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import re
from typing import Any, Iterable, Mapping


def normalize_identity_value(value: str) -> str:
    """Normalize punctuation/case while preserving variant-significant characters."""
    return re.sub(r"[^A-Z0-9]+", "", str(value or "").upper())


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split())


class EvidenceState(str, Enum):
    MATCH = "match"
    CONFLICT = "conflict"
    MISSING = "missing"


class VerificationLevel(str, Enum):
    EXACT_VARIANT = "exact_variant"
    EXACT_MODEL = "exact_model"
    FAMILY_ONLY = "family_only"
    CONFLICT = "conflict"
    INSUFFICIENT = "insufficient"


@dataclass(frozen=True)
class VariantAttributes:
    """Extensible variant map. Unknown future fields are deliberately retained."""

    values: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        cleaned = {
            str(key): value
            for key, value in self.values.items()
            if value not in (None, "", [], (), {})
        }
        object.__setattr__(self, "values", cleaned)

    def get(self, key: str, default: Any = "") -> Any:
        return self.values.get(key, default)

    def to_dict(self) -> dict[str, Any]:
        return dict(self.values)


@dataclass(frozen=True)
class CategorySchema:
    key: str
    aliases: tuple[str, ...] = ()
    significant_variant_fields: tuple[str, ...] = ()

    def matches(self, category: str) -> bool:
        value = category.casefold().strip()
        return value == self.key.casefold() or any(alias.casefold() in value for alias in self.aliases)


@dataclass(frozen=True)
class BrandConfig:
    brand: str
    aliases: tuple[str, ...] = ()
    identity_strategy: str = "model_and_variants"
    category_variant_fields: Mapping[str, tuple[str, ...]] = field(default_factory=dict)

    def variant_fields_for(self, schema: CategorySchema) -> tuple[str, ...]:
        return self.category_variant_fields.get(schema.key, schema.significant_variant_fields)


DEFAULT_CATEGORY_SCHEMAS = (
    CategorySchema("smartphone", ("smartphone", "смартфон", "телефон"), ("color", "ram", "storage", "region")),
    CategorySchema("laptop", ("laptop", "ноутбук"), ("color", "ram", "storage", "configuration", "region")),
    CategorySchema("graphics_card", ("graphics card", "видеокарт"), ("hardware_revision", "configuration")),
    CategorySchema("case", ("case", "чехол"), ("color", "size", "configuration")),
    CategorySchema("display", ("monitor", "монитор", "телевизор", "display"), ("screen_size", "region")),
    CategorySchema("network_device", ("router", "роутер", "маршрутизатор", "адаптер"), ("hardware_revision", "region")),
    CategorySchema("bosch_home", ("духовой", "варочная", "холодиль", "посудомоеч", "стираль", "сушиль", "вытяжк"), ("service_index", "region")),
    CategorySchema("bosch_tools", ("дрель", "шуруповерт", "перфоратор", "лобзик", "шлифов", "пила", "инструмент"), ("hardware_revision", "configuration")),
    CategorySchema("generic", (), ()),
)


def category_schema(category: str, schemas: Iterable[CategorySchema] = DEFAULT_CATEGORY_SCHEMAS) -> CategorySchema:
    return next((schema for schema in schemas if schema.key != "generic" and schema.matches(category)), CategorySchema("generic"))


def extract_variant_attributes(title: str, *codes: str) -> VariantAttributes:
    """Extract only high-confidence, syntax-driven variant evidence."""
    text = _clean(" ".join((title, *codes)))
    values: dict[str, Any] = {}
    memory = re.search(r"(?i)(\d{1,3})\s*(?:GB|ГБ)\s*[+/]\s*(\d{2,4})\s*(?:GB|ГБ)", text)
    if memory:
        values["ram"], values["storage"] = f"{memory.group(1)}GB", f"{memory.group(2)}GB"
    screen = re.search(r"(?i)(?<!\d)(\d{2}(?:[.,]\d)?)\s*(?:\"|inch|дюйм)", text)
    if screen:
        values["screen_size"] = screen.group(1).replace(",", ".")
    revision = re.search(r"(?i)\b(?:REV(?:ISION)?\.?\s*)?(V\d+(?:\.\d+)?)\b", text)
    if revision:
        values["hardware_revision"] = revision.group(1).upper()
    service = next((match for code in codes if (match := re.search(r"/([0-9]{2})(?:\b|$)", code or ""))), None)
    if service:
        values["service_index"] = service.group(1)
    if re.search(r"(?i)\b(bundle|kit|комплект|набор)\b", text):
        values["bundle_components"] = _clean(title)
    return VariantAttributes(values)


@dataclass(frozen=True)
class ProductIdentity:
    brand_raw: str
    brand_canonical: str
    category_raw: str
    category_canonical: str
    seller_sku: str
    wb_sku: str
    title_raw: str
    model_candidates: tuple[str, ...]
    variant_attributes: VariantAttributes = field(default_factory=VariantAttributes)
    market: str = ""
    marketing_models: tuple[str, ...] = ()
    identity_semantics_version: str = "legacy"
    model_qualifiers: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["variant_attributes"] = self.variant_attributes.to_dict()
        return result

    @classmethod
    def from_product(cls, product: Mapping[str, Any], *, market: str = "") -> "ProductIdentity":
        brand = _clean(product.get("brand", ""))
        category = _clean(product.get("category", ""))
        title = _clean(product.get("name", ""))
        seller_sku = _clean(product.get("search_code", product.get("seller_sku", "")))
        alternate = _clean(product.get("alternate_code", ""))
        explicit = product.get("model_candidates") or ()
        if isinstance(explicit, str):
            explicit = (explicit,)
        title_codes = re.findall(r"(?<![\w])([A-Za-z0-9][A-Za-z0-9./_-]{4,})(?![\w])", title)
        candidates = tuple(dict.fromkeys(x for x in (seller_sku, alternate, *explicit, *title_codes) if x))
        variants = product.get("variant_attributes")
        if not isinstance(variants, VariantAttributes):
            variants = VariantAttributes(variants or extract_variant_attributes(title, *candidates).to_dict())
        return cls(
            brand_raw=brand,
            brand_canonical=brand.casefold(),
            category_raw=category,
            category_canonical=category_schema(category).key,
            seller_sku=seller_sku,
            wb_sku=_clean(product.get("wb_sku", "")),
            title_raw=title,
            model_candidates=candidates,
            variant_attributes=variants,
            market=_clean(product.get("market", market)),
        )


@dataclass(frozen=True)
class PageIdentity:
    seller_sku: str = ""
    manufacturer_sku: str = ""
    model_code: str = ""
    family: str = ""
    ean_gtin: str = ""
    variant_attributes: VariantAttributes = field(default_factory=VariantAttributes)
    structured_product_name: str = ""
    structured_brand: str = ""
    category_compatible: bool = False
    source_brand_verified: bool = False


@dataclass(frozen=True)
class IdentityEvidence:
    evidence_type: str
    raw_value: str
    normalized_value: str
    source: str
    extraction_method: str
    confidence: float
    state: EvidenceState

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["state"] = self.state.value
        return value


@dataclass(frozen=True)
class IdentityVerification:
    level: VerificationLevel
    evidence: tuple[IdentityEvidence, ...]
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "level": self.level.value,
            "evidence": [item.to_dict() for item in self.evidence],
            "reason": self.reason,
        }


class IdentityVerifier:
    def verify(
        self,
        expected: ProductIdentity,
        observed: PageIdentity,
        *,
        source: str,
        extraction_method: str = "adapter",
        schema: CategorySchema | None = None,
        brand_config: BrandConfig | None = None,
    ) -> IdentityVerification:
        schema = schema or category_schema(expected.category_raw)
        fields = brand_config.variant_fields_for(schema) if brand_config else schema.significant_variant_fields
        fields = tuple(dict.fromkeys((*fields, *expected.variant_attributes.values)))
        evidence: list[IdentityEvidence] = []

        expected_models = {normalize_identity_value(x) for x in expected.model_candidates if x}
        observed_models = {
            normalize_identity_value(x)
            for x in (observed.manufacturer_sku, observed.model_code)
            if x
        }
        model_state = EvidenceState.MISSING
        if observed_models:
            model_state = EvidenceState.MATCH if expected_models & observed_models else EvidenceState.CONFLICT
        evidence.append(IdentityEvidence(
            "model_code", ", ".join(filter(None, (observed.manufacturer_sku, observed.model_code))),
            ",".join(sorted(observed_models)), source, extraction_method, 1.0, model_state,
        ))

        if expected.identity_semantics_version == "7.1.0":
            # New semantics retain significant model punctuation and reject mixed identifiers.
            canonical = lambda value: " ".join(str(value).upper().split())
            wanted = {canonical(x) for x in expected.model_candidates}
            # An absent declared region/service suffix is missing variant evidence,
            # not a different base model. A different explicit suffix still conflicts.
            for full_model in tuple(wanted):
                for variant_key in ("region", "service_index"):
                    suffix = canonical(expected.variant_attributes.get(variant_key))
                    if suffix and full_model.endswith("/" + suffix):
                        wanted.add(full_model[:-(len(suffix) + 1)])
            found = {canonical(x) for x in (observed.manufacturer_sku, observed.model_code) if x}
            model_state = (EvidenceState.MATCH if found <= wanted else EvidenceState.CONFLICT) if found else EvidenceState.MISSING
            evidence[0] = IdentityEvidence("model_code", ", ".join(sorted(found)), ",".join(sorted(found)), source, extraction_method, 1.0, model_state)
            name = observed.structured_product_name
            brand_ok = observed.source_brand_verified and (not observed.structured_brand or normalize_identity_value(observed.structured_brand) == normalize_identity_value(expected.brand_raw))
            matches = [model for model in expected.marketing_models if any(c.isdigit() for c in model) and re.search(r"(?<!\w)" + r"[\s_]+".join(re.escape(x) for x in model.split()) + r"(?!\w)", name, re.I)]
            qualifier_conflict = any(
                re.search(r"(?<!\w)" + r"[\s_]+".join(re.escape(x) for x in model.split()) + r"[\s_-]+" + re.escape(qualifier) + r"(?!\w)", name, re.I)
                for model in matches for qualifier in expected.model_qualifiers
                if not re.search(r"(?<!\w)" + re.escape(qualifier) + r"(?!\w)", model, re.I)
            )
            if qualifier_conflict and brand_ok and observed.category_compatible:
                model_state = EvidenceState.CONFLICT
                evidence.append(IdentityEvidence("model_qualifier", name, normalize_identity_value(name), source, extraction_method, .95, EvidenceState.CONFLICT))
            if matches and brand_ok and observed.category_compatible and model_state != EvidenceState.CONFLICT:
                model_state = EvidenceState.MATCH
                evidence.append(IdentityEvidence("structured_product_name", name, normalize_identity_value(name), source, extraction_method, .95, EvidenceState.MATCH))

        if observed.seller_sku:
            seller_state = EvidenceState.MATCH if normalize_identity_value(observed.seller_sku) == normalize_identity_value(expected.seller_sku) else EvidenceState.CONFLICT
            evidence.append(IdentityEvidence("seller_sku", observed.seller_sku, normalize_identity_value(observed.seller_sku), source, extraction_method, .8, seller_state))
        else:
            evidence.append(IdentityEvidence("seller_sku", "", "", source, extraction_method, .8, EvidenceState.MISSING))

        variant_conflict = False
        missing_variant = False
        expected_variant_count = 0
        for name in fields:
            wanted = expected.variant_attributes.get(name)
            found = observed.variant_attributes.get(name)
            if wanted in (None, ""):
                continue
            expected_variant_count += 1
            if found in (None, ""):
                state = EvidenceState.MISSING
                missing_variant = True
            else:
                state = EvidenceState.MATCH if normalize_identity_value(str(wanted)) == normalize_identity_value(str(found)) else EvidenceState.CONFLICT
                variant_conflict |= state == EvidenceState.CONFLICT
            evidence.append(IdentityEvidence(name, str(found or ""), normalize_identity_value(str(found or "")), source, extraction_method, .9, state))

        if model_state == EvidenceState.CONFLICT or variant_conflict:
            return IdentityVerification(VerificationLevel.CONFLICT, tuple(evidence), "Structured model or variant evidence conflicts.")
        if model_state == EvidenceState.MATCH:
            if expected_variant_count and not missing_variant:
                return IdentityVerification(VerificationLevel.EXACT_VARIANT, tuple(evidence), "Model and all significant expected variant fields match.")
            return IdentityVerification(VerificationLevel.EXACT_MODEL, tuple(evidence), "Model matches; significant variant evidence is absent or incomplete.")

        if expected.identity_semantics_version == "7.1.0" and observed.structured_product_name and observed.source_brand_verified and observed.category_compatible and (not observed.structured_brand or normalize_identity_value(observed.structured_brand) == normalize_identity_value(expected.brand_raw)):
            for marketing in expected.marketing_models:
                tokens = marketing.split()
                family = " ".join(tokens[:next((i + 1 for i, token in enumerate(tokens) if any(c.isdigit() for c in token)), len(tokens))])
                if family != marketing and re.search(r"(?<!\w)" + re.escape(family) + r"(?!\w)", observed.structured_product_name, re.I):
                    return IdentityVerification(VerificationLevel.FAMILY_ONLY, tuple(evidence), "Only the marketing family matches; model qualifiers are missing.")

        expected_family = normalize_identity_value(expected.model_candidates[0]) if expected.model_candidates else ""
        observed_family = normalize_identity_value(observed.family)
        if expected_family and observed_family and expected_family == observed_family:
            return IdentityVerification(VerificationLevel.FAMILY_ONLY, tuple(evidence), "Only an explicit family identifier matches.")
        return IdentityVerification(VerificationLevel.INSUFFICIENT, tuple(evidence), "There is not enough structured identity evidence.")


def bosch_service_identity(code: str) -> tuple[str, str]:
    """Return Bosch base E-Nr and its significant service index."""
    value = _clean(code).upper()
    match = re.fullmatch(r"(.+?)/([0-9]{2})", value)
    return (match.group(1), match.group(2)) if match else (value, "")
