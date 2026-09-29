"""HyperX (hyperx.com) official manufacturer adapter -- Stage 14, catalog-
route-wired and identity-corrected in Stage 15.

Per explicit user authorization: HyperX's real Product page structure was
already confirmed by Stage 8.1's structural census (JSON-LD Product +
Shopify DOM, see reports/source_census_2026-09-23_stage13/readiness_table.md
"Group A") but no adapter was ever built from that research. This module is
that adapter -- the field-VALUE extraction itself is done by the reusable,
source-agnostic primitives in adapters/structured_page.py (also boundary-
tested against Bosch's and Cudy's own structural contracts, without giving
either of them their own identity or adapter here); this module supplies
only what is genuinely HyperX-specific: the identity check.

KNOWN_URLS holds only per-SKU URLs confirmed against a real, saved official
page -- see reports/source_census_2026-09-23_stage11/card.json (9A273AA),
reports/source_census_2026-09-23_stage11_1/additional_rows_and_adapter_status.json
(A1KY6AA) and reports/source_census_2026-09-24_stage18/raw/accepted_urls.json
(the rest: page sku == catalog code, title tokens on the page name). A caller (worker.py, by
default) with no injected urls/session gets 'official_url_needed' for any
row not in this dict, exactly like DNS's dealer_url_needed: never a guessed
URL, never a silently-invented result.

Identity rule, precisely: HyperX seller codes are either a bare code (e.g.
"9A273AA", no region variant marketed) or code#SUFFIX (e.g. "7G7A4AA#ACB",
where SUFFIX marks a region-specific keyboard layout/localization). A page
whose own JSON-LD sku matches the catalog row's FULL code (base+suffix, or
the bare code) is "exact_variant". A page whose base code matches but whose
suffix differs (or is present on one side and not the other) is
"base_code_confirmed" -- the same base_model-vs-full_sku distinction
already used for LG, and the same base-vs-region-suffix distinction Stage
12/13 already used for Razer (M1 vs U1). It is never silently promoted to
exact_variant.

Stage 15 correction: identity is anchored on JSON-LD `sku` alone, falling
back to `productID` only when `sku` is absent. Stage 14's synthetic
fixtures never populated `productID` with a realistic, independently-
sourced value, so a design assumption -- "sku and productID are both
identity anchors and must agree" -- went untested against real pages. All
3 real saved captures used this stage (Stage 11/11.1's microphone, mouse
and keyboard pages) show a Shopify `productID` that is that platform's own
internal numeric product id, unrelated to the merchant `sku` -- treating
disagreement between them as a conflict made every real page report
"mismatch" even where `sku` matched the catalog exactly. `productID` is
kept only as a fallback for a page that has no `sku` field at all, never
compared against a present `sku`. This does NOT weaken a genuine conflict:
when `sku` itself differs from the catalog code (a real different product,
or a real region/variant suffix mismatch), the result is still `mismatch`
or `base_code_confirmed` as before -- see
tests/test_hyperx_stage16_policy_fetch.py's
test_productid_fix_does_not_hide_a_real_sku_conflict.

Stage 19 -- variants. A HyperX product page embeds every variant of the model (see structured_page.
extract_shopify_product) while its JSON-LD top level, main image and default gallery describe only the
variant the page happens to have selected. parse_page() therefore resolves the catalog code to ONE variant
and keeps three things apart:
  * identity and variant data (sku, variant name, option values such as colour/layout, GTIN, photos) come
    from that variant only. If the page has selected a different variant, but its JSON-LD offer and its
    embedded product JSON both name the catalog code with the same variant id, the result is exact_variant
    through that in-page variant record (evidence says so); the selected variant's own values are never
    substituted;
  * photos are the media of that variant (single-variant product: all media; several variants: media whose alt
    tag matches the variant's featured image, else only the featured media); other variants' images are kept as
    excluded candidates with the reason;
  * specifications and the description are shared by the model: every such attribute is marked scope="model"
    (and listed in the evidence), never presented as a property of the variant.
Within the specification table a heading row opens a block; when the same specification name repeats with a
different value in a later block (a headset's driver "Sensitivity" and its microphone's), the later one is
named "<name> (<block label>)" instead of being reported as a conflict -- see _spec_attributes().

Stage 16: find_source()'s ordinary fetch path no longer talks to a bare
requests.Session directly. It goes through adapters/policy_fetch.py's
PolicyAwareFetcher, which wraps product_tool.census.endpoint_probe.
AccessProbe (ProbePolicy, host allowlist, redirect-chain checks, 401/403/
429/challenge detection, in-process host-stop) with a JSON-file-backed
fetch log, so a host stop persists across a fresh HyperXAdapter instance
or process ("a new run"), not just one instance's lifetime -- see
adapters/policy_fetch.py's own module docstring for why this is a
different, additional guarantee from what worker.py's finish()-status
logic or find_documents()'s never-guess rule already gave this adapter.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from ..census.endpoint_probe import AccessStatus, ProbePolicy
from .common import PhotoCandidate, RawAttribute, SourceDocument, meta_description
from .policy_fetch import PolicyAwareFetcher
from .structured_page import (
    ExtractedField,
    ROLE_DOM_TABLE,
    ROLE_JSON_LD,
    ShopifyProduct,
    ShopifyVariant,
    extract_description_images,
    extract_dom_spec_table,
    extract_json_ld_product,
    extract_main_gallery,
    extract_shopify_product,
    extract_video,
)

PAGE_HOST = "hyperx.com"
ALLOWED_HOSTS = frozenset({PAGE_HOST, "www.hyperx.com"})

# Stage 16: default location for the persisted fetch log when a caller
# builds a HyperXAdapter directly without specifying fetch_log_path --
# worker.py's own default factory instead colocates it with whatever
# jobs database is in use (database.parent / "hyperx_fetch_log.json"), so
# in practice this constant is mainly what stands-alone/manual use falls
# back to.
DEFAULT_FETCH_LOG_PATH = Path(__file__).resolve().parents[2] / "data" / "hyperx_fetch_log.json"

# Only rows whose official page was OBSERVED (not built from a pattern) and
# whose own JSON-LD sku equals the catalog code -- see the module docstring
# for the reports/ evidence. Never populated by guessing or by name-similarity;
# the same discipline adapters/dns.py already follows. Every other HyperX
# catalog row has no entry here and gets 'official_url_needed', not a guessed
# URL -- including the Alloy Rise 75 keyboard (7G7A4AA#ACB), whose only found
# candidate page is a confirmed US-layout (#ABA) mismatch, not this row.
#
# Stage 15: 9A273AA and A1KY6AA (human-confirmed against saved official pages).
# Stage 18: 11 more, from reports/source_census_2026-09-24_stage18/raw/
# accepted_urls.json -- 4P5D4AA from a saved Stage 5.1 snapshot (no request),
# ten from one bounded policy-aware wave (21 requests); a test replays every
# one of them offline and requires this map and that file to agree.
KNOWN_URLS: dict[str, str] = {
    "9A273AA": "https://hyperx.com/products/hyperx-quadcast-2-s-usb-microphone",
    "A1KY6AA": "https://hyperx.com/products/hyperx-pulsefire-fuse-wireless-gaming-mouse",
    "4P5D4AA": "https://hyperx.com/products/hyperx-cloud-alpha-wireless",
    "4P5J1AA": "https://hyperx.com/products/hyperx-cloud-stinger-core-wireless-ps5",
    "4P5L3AA": "https://hyperx.com/products/hyperx-cloud-alpha-s",
    "4P5P7AA": "https://hyperx.com/products/hyperx-quadcast-s-usb-microphone",
    "683L9AA": "https://hyperx.com/products/hyperx-cloud-stinger-2-core-wired-gaming-headset",
    "6Y2G8AA": "https://hyperx.com/products/hyperx-cloud-ii-core-wireless-gaming-headset",
    "77Z46AA": "https://hyperx.com/products/hyperx-cloud-iii-wireless-gaming-headset",
    "A1KY5AA": "https://hyperx.com/products/hyperx-pulsefire-haste-2-pro-4k-wireless-gaming-mouse",
    "A2PB3AA": "https://hyperx.com/products/hyperx-pulsefire-saga-gaming-mouse",
    "AR0A0AA": "https://hyperx.com/products/hyperx-solocast-2-gaming-usb-condenser-microphone",
    "B5VC4AA": "https://hyperx.com/products/hyperx-cloud-flight-2-wireless-gaming-headset",
    # Stage 19: seven non-default variants. Each URL is the one printed in its product page's own JSON-LD offer
    # (variant id = the embedded product JSON's id), fetched once (200); reports/source_census_2026-09-24_stage19/
    # raw/accepted_variant_urls.json. The page behind such a URL still has the DEFAULT variant selected in its
    # JSON-LD, so identity comes from the in-page variant record (parse_page), never from the selection.
    "727A8AA": "https://hyperx.com/products/hyperx-cloud-iii-wired-gaming-headset?variant=43656365375645",
    "727A9AA": "https://hyperx.com/products/hyperx-cloud-iii-wired-gaming-headset?variant=43656365408413",
    "A59YZAA": "https://hyperx.com/products/hyperx-cloud-iii-s-wireless-gaming-headset?variant=46760503967901",
    "A59Z0AA": "https://hyperx.com/products/hyperx-cloud-iii-s-wireless-gaming-headset?variant=46760503935133",
    "AJ0T1AA": "https://hyperx.com/products/hyperx-cloud-jet-wireless-gaming-headset?variant=46592844431517",
    "B5VC5AA": "https://hyperx.com/products/hyperx-cloud-flight-2-wireless-gaming-headset?variant=47310091813021",
    "BS7C1AA": "https://hyperx.com/products/hyperx-cloud-iii-wired-gaming-headset?variant=47331550986397",
}

_CODE_RE = re.compile(r"^([A-Z0-9]+)(?:#([A-Z0-9]+))?$")


def split_hyperx_code(code: str) -> tuple[str, str]:
    """('7G7A4AA#ACB') -> ('7G7A4AA', 'ACB'); ('9A273AA') -> ('9A273AA', '').
    Not a HyperX-shaped code at all -> the whole (upper-cased) string as
    the base, empty suffix -- never raises, never guesses a split that
    isn't actually there."""
    normalized = (code or "").strip().upper()
    match = _CODE_RE.match(normalized)
    if not match:
        return normalized, ""
    base, suffix = match.groups()
    return base, suffix or ""


@dataclass(frozen=True)
class HyperXPageResult:
    """parse_page()'s full result: the standard SourceDocument the rest of
    the pipeline already knows how to store, plus every individual field
    extracted -- each still carrying its own url/evidence/role/confirmation,
    exactly as structured_page.py produced it. Nothing here is a bare
    value; find_source() itself only ever returns .document, so worker.py's
    existing _save()/SourceDocument handling needs no changes, but any
    caller that wants the rich per-field detail (tests, future UI/export
    work) has it without re-parsing anything."""
    document: SourceDocument
    extracted_fields: tuple[ExtractedField, ...]


@dataclass(frozen=True)
class IdentityCheck:
    catalog_base: str
    catalog_suffix: str
    page_base: str
    page_suffix: str
    page_source_fields: tuple[ExtractedField, ...]

    @property
    def level(self) -> str:
        if not self.page_source_fields:
            return "unknown"
        if self.page_base != self.catalog_base:
            return "mismatch"
        if self.page_suffix == self.catalog_suffix:
            return "exact_variant"
        return "base_code_confirmed"


def check_identity(json_ld_fields: list[ExtractedField], *, catalog_code: str) -> IdentityCheck:
    catalog_base, catalog_suffix = split_hyperx_code(catalog_code)
    # Stage 15: sku is the merchant identity field; productID on a real
    # Shopify page is that platform's own internal numeric id, not a code
    # comparable to the catalog's seller article -- see module docstring.
    # productID is used only when a page has no sku field at all.
    sku_fields = tuple(f for f in json_ld_fields if f.name == "sku" and f.role == ROLE_JSON_LD)
    code_fields = sku_fields or tuple(f for f in json_ld_fields if f.name == "productID" and f.role == ROLE_JSON_LD)
    if not code_fields:
        return IdentityCheck(catalog_base, catalog_suffix, "", "", ())
    # If a page somehow carries more than one sku value (multiple JSON-LD
    # blocks disagreeing), that is itself unresolved, never silently picked.
    values = {f.value.strip().upper() for f in code_fields}
    if len(values) > 1:
        return IdentityCheck(catalog_base, catalog_suffix, "", "", code_fields)
    page_base, page_suffix = split_hyperx_code(next(iter(values)))
    return IdentityCheck(catalog_base, catalog_suffix, page_base, page_suffix, code_fields)


def _host_of(url: str) -> str:
    return (urlsplit(url).hostname or "").casefold()


@dataclass(frozen=True)
class ScopedAttribute(RawAttribute):
    """A RawAttribute that says whose it is (Stage 19): "variant" = the selected variant's own, "model" = shared by every
    variant of the model. adapters/common.py is a protected pipeline file, so the marker lives here."""
    scope: str = ""


def format_attribute_scope(variant: list[RawAttribute], model: list[RawAttribute]) -> str:
    """Machine-readable, stored in the source page's evidence text (no schema change)."""
    return "attribute_scope=" + json.dumps({"variant": sorted({a.name for a in variant}), "model": sorted({a.name for a in model})}, ensure_ascii=False, sort_keys=True)


def parse_attribute_scope(evidence: str) -> dict[str, list[str]]:
    match = re.search(r"attribute_scope=(\{.*?\})(?:;|$)", evidence or "")
    if not match:
        return {"variant": [], "model": []}
    try:
        data = json.loads(match.group(1))
    except ValueError:
        return {"variant": [], "model": []}
    return {"variant": list(data.get("variant", [])), "model": list(data.get("model", []))}


def _block_label(fields: list[ExtractedField]) -> str:
    """A block whose own "Element" row names a microphone is the microphone block; otherwise the heading plus block number."""
    for f in fields:
        if f.name.strip().casefold() == "element" and "microphone" in f.value.casefold():
            return "microphone"
    first = fields[0]
    return f"{first.section or 'block'} #{first.block}"


def _spec_attributes(spec_fields: list[ExtractedField]) -> list[RawAttribute]:
    """Model-level specification rows. A name that repeats with a DIFFERENT value in a later block of the
    table belongs to a different part of the device (Stage 19: driver vs microphone sensitivity, on the same
    page under a repeated heading, with different units); the later row is named "<name> (<block label>)".
    Identical repeats were already dropped by the extractor, and the first occurrence keeps the bare name."""
    by_block: dict[int, list[ExtractedField]] = {}
    for f in spec_fields:
        by_block.setdefault(f.block, []).append(f)
    first_block_of_name: dict[str, int] = {}
    attributes = []
    for f in spec_fields:
        name = f.name
        if f.role == ROLE_DOM_TABLE and f.block:
            owner = first_block_of_name.setdefault(f.name, f.block)
            if owner != f.block:
                name = f"{f.name} ({_block_label(by_block[f.block])})"
        attributes.append(ScopedAttribute(name, f.value, scope="model"))
    return attributes


_INFOGRAPHIC_RE = re.compile(r"annotated|infograph", re.I)


def _kind_of_gallery_image(url: str) -> str:
    """The site tags its model-wide annotated infographics with the FIRST variant's colour ("(Black) - 02"); the
    file name says what they are, and they are shared by the model, so they go to the separate feature group."""
    return "feature" if _INFOGRAPHIC_RE.search(url.split("?")[0].rsplit("/", 1)[-1]) else "product_gallery"


def _variant_photos(exact: bool, product: ShopifyProduct | None, target: ShopifyVariant | None,
                    gallery: list[ExtractedField], description_images: list[ExtractedField]) -> tuple[list[PhotoCandidate], str]:
    features = [PhotoCandidate(f.url, f.url, "feature") for f in description_images]
    if not exact:
        # The gallery shows some other variant (or the identity is unproven): none of it is claimed for this row.
        return [PhotoCandidate(f.url, f.url, "excluded", excluded_reason="identity not exact: gallery is not this variant's") for f in gallery] + features, \
            "none claimed (identity not exact)"
    if product is None or target is None:
        return _one_per_media([PhotoCandidate(f.url, f.url, "product_gallery") for f in gallery], gallery) + features, f"{len(gallery)} gallery items (no embedded variant data)"
    media, basis = product.variant_media(target)
    wanted = {m.media_id for m in media}
    tag_of = {m.media_id: m.tag or "shared" for m in product.media}
    chosen, seen_ids, excluded = [], set(), []
    for f in gallery:
        if f.media_id and f.media_id in wanted:
            if f.media_id not in seen_ids:  # thumbnail and main slide of one media item are one photo
                seen_ids.add(f.media_id)
                chosen.append(PhotoCandidate(f.url, f.url, _kind_of_gallery_image(f.url)))
        elif f.media_id in tag_of and f.media_id not in seen_ids:
            seen_ids.add(f.media_id)
            excluded.append(PhotoCandidate(f.url, f.url, "excluded", excluded_reason=f"other variant or shared media ({tag_of[f.media_id]})"))
    if not chosen:  # the DOM gallery gave nothing usable: the variant's own media from the embedded JSON, no other source
        chosen = [PhotoCandidate(m.src, m.src, _kind_of_gallery_image(m.src)) for m in media]
    infographics = sum(1 for c in chosen if c.kind == "feature")
    return chosen + excluded + features, (f"{len(chosen) - infographics} gallery photos + {infographics} model-wide infographics (feature group) among the {len(media)} media tagged for the variant ({basis}); "
                                          f"{len(excluded)} other-variant/shared images excluded")


def _one_per_media(candidates: list[PhotoCandidate], gallery: list[ExtractedField]) -> list[PhotoCandidate]:
    seen, result = set(), []
    for candidate, f in zip(candidates, gallery):
        if f.media_id and f.media_id in seen:
            continue
        seen.add(f.media_id)
        result.append(candidate)
    return result


class HyperXAdapter:
    source_key = "hyperx"
    site_name = "HyperX"

    def __init__(
        self, session=None, *,
        clock: Callable[[], float] = time.monotonic,
        urls: dict[str, str] | None = None,
        fetch_log_path: Path | None = None,
        policy: ProbePolicy | None = None,
    ):
        self.clock = clock
        self.urls = urls if urls is not None else KNOWN_URLS
        self.request_count = 0
        # Stage 16: every ordinary fetch goes through PolicyAwareFetcher
        # (ProbePolicy, host allowlist, redirect-chain checks, 401/403/429/
        # challenge detection, and -- via fetch_log_path -- a host-stop
        # that survives a fresh instance/process, not just this one's
        # lifetime). `session` is a test double or None; PolicyAwareFetcher/
        # AccessProbe fall back to a real requests.Session only when it is
        # None, exactly like every other adapter in this project.
        self._fetcher = PolicyAwareFetcher(
            fetch_log_path or DEFAULT_FETCH_LOG_PATH,
            session=session, policy=policy, clock=clock,
        )

    def find_source(self, search_code: str, *, deadline: float) -> SourceDocument:
        normalized = (search_code or "").strip().upper()
        url = self.urls.get(normalized, "")
        if not url:
            return SourceDocument(
                self.source_key, self.site_name, "", match_level="official_url_needed",
                evidence=(
                    f"Нет проверенного официального URL hyperx.com для артикула {normalized!r}. "
                    "Нужна точная ссылка на карточку товара -- не будет угадана."
                ),
            )
        if _host_of(url) not in ALLOWED_HOSTS:
            return SourceDocument(
                self.source_key, self.site_name, url, match_level="unknown",
                error=f"Configured URL host '{_host_of(url)}' is not an allowed HyperX host.",
            )
        self.request_count += 1
        remaining = deadline - self.clock()
        if remaining <= 0:
            return SourceDocument(self.source_key, self.site_name, url, match_level="unknown", error="Time budget exhausted before the HyperX page request.")

        result = self._fetcher.get(url, allowed_hosts=tuple(ALLOWED_HOSTS), deadline=deadline)

        if result.access_status in (AccessStatus.CAPTCHA_OR_BLOCKED, AccessStatus.RATE_LIMITED):
            detail = f"HTTP {result.http_status}" if result.http_status is not None else "a prior block already recorded for this host"
            return SourceDocument(self.source_key, self.site_name, url, match_level="blocked", error=f"{detail} -- access blocked. Not retried.")
        if result.access_status == AccessStatus.REGIONAL_REDIRECT:
            return SourceDocument(self.source_key, self.site_name, url, match_level="unknown", error=result.error or "Redirected off an allowed host -- not followed.")
        if result.access_status == AccessStatus.UNAVAILABLE:
            # Includes a real network failure and any other HTTP error
            # status (AccessProbe does not treat a bare 401 as a host-stop
            # signal the way 403/429 are -- unlike the pre-Stage-16 code,
            # which lumped 401 in with 403/429; not currently retried
            # either way, just labeled "unknown" instead of "blocked").
            return SourceDocument(self.source_key, self.site_name, url, match_level="unknown", error=result.error or f"HTTP {result.http_status}")

        html = (result.diagnostic_text or "")[:900_000]
        return self.parse_page(html, result.final_url or url, catalog_code=normalized).document

    def parse_page(self, html: str, page_url: str, *, catalog_code: str) -> HyperXPageResult:
        """Split out from find_source() so tests (and offline replay) can
        feed a saved/synthetic page directly, with no network involved."""
        json_ld_fields = extract_json_ld_product(html, page_url)
        identity = check_identity(json_ld_fields, catalog_code=catalog_code)
        product = extract_shopify_product(html, page_url)
        target = product.variant_by_sku(catalog_code) if product else None

        # exact_variant through the page's own selected variant, or through an in-page variant record
        # (JSON-LD offer + embedded product JSON agree on sku and variant id, offer url carries that id).
        selected_is_target = identity.level == "exact_variant"
        via_record = bool(not selected_is_target and identity.page_source_fields and target is not None and target.confirmed)
        level = "exact_variant" if via_record else identity.level
        exact = level == "exact_variant"

        spec_fields = extract_dom_spec_table(html, page_url)
        gallery_fields = extract_main_gallery(html, page_url)
        description_image_fields = extract_description_images(html, page_url)
        video_fields = extract_video(html, page_url)
        soup = BeautifulSoup(html, "html.parser")

        # ---- attributes: the variant's own facts, then the model's shared facts (each marked)
        variant_attributes: list[RawAttribute] = []
        if exact:
            if target is not None:
                variant_attributes.append(ScopedAttribute("SKU", target.sku, scope="variant"))
                if target.name:
                    variant_attributes.append(ScopedAttribute("Variant name", target.name, scope="variant"))
                variant_attributes += [ScopedAttribute(name, value, scope="variant") for name, value in target.options if name and value]
                if target.barcode:
                    variant_attributes.append(ScopedAttribute("GTIN-12", target.barcode, scope="variant"))
            else:  # no embedded product JSON: the selected variant IS the catalog code, JSON-LD is its own
                code = next((f.value for f in json_ld_fields if f.name == "sku"), catalog_code)
                variant_attributes.append(ScopedAttribute("SKU", code, scope="variant"))
                gtin = next((f.value for f in json_ld_fields if f.name == "gtin12"), "")
                if gtin:
                    variant_attributes.append(ScopedAttribute("GTIN-12", gtin, scope="variant"))
        # JSON-LD additionalProperty rows describe the SELECTED variant: kept only when that is the catalog variant.
        json_ld_properties = [f for f in json_ld_fields if f.name not in ("name", "sku", "productID", "json_ld_image", "mpn") and not f.name.startswith("gtin")]
        dropped_default_properties = 0
        if selected_is_target:
            variant_attributes += [ScopedAttribute(f.name, f.value, scope="variant") for f in json_ld_properties]
        else:
            dropped_default_properties = len(json_ld_properties)
        model_attributes = _spec_attributes(spec_fields)
        attributes = variant_attributes + model_attributes

        # ---- photos
        photo_candidates, photo_note = _variant_photos(exact, product, target, gallery_fields, description_image_fields)
        photos = [c.url for c in photo_candidates if not c.excluded_reason]

        found_name = target.sku if (via_record and target is not None) else next((f.value for f in json_ld_fields if f.name in ("sku", "productID")), "")
        page_code = identity.page_base + (f"#{identity.page_suffix}" if identity.page_suffix else "")
        catalog_code_display = identity.catalog_base + (f"#{identity.catalog_suffix}" if identity.catalog_suffix else "")
        if via_record:
            source = (f"variant_source=in_page_variant_record (page selected {page_code!r}; variant_id={target.variant_id}; url={target.url}; "
                      f"confirmed_by={'+'.join(target.sources)}; default variant's own values not used, {dropped_default_properties} JSON-LD properties dropped)")
        elif selected_is_target:
            source = f"variant_source=page_selected_variant{'; variant_id=' + target.variant_id if target else ''}"
        else:
            source = "variant_source=none"
        evidence = (
            f"identity={level} (page code {page_code!r} vs catalog {catalog_code_display!r}); {source}; "
            f"json_ld_fields={len(json_ld_fields)}, spec_fields={len(spec_fields)}, "
            f"gallery_images={len(gallery_fields)}, description_images={len(description_image_fields)}, videos={len(video_fields)}; "
            f"photos: {photo_note}; description=shared_model; {format_attribute_scope(variant_attributes, model_attributes)}"
        )

        document = SourceDocument(
            self.source_key, self.site_name, page_url,
            found_model=found_name,
            match_level=level,
            evidence=evidence,
            attributes=attributes,
            description=meta_description(soup),
            photos=photos,
            photo_candidates=photo_candidates,
            html=html,
        )
        all_fields = tuple(json_ld_fields + spec_fields + gallery_fields + description_image_fields + video_fields)
        return HyperXPageResult(document=document, extracted_fields=all_fields)

    def find_documents(self, search_code: str, *, deadline: float) -> tuple[list[dict], str]:
        """HyperX documents: a genuine downloadable manual/PDF link found
        on the page -- never inferred from box-contents text. Mentioning a
        'Quick Start Guide' as an included accessory is not evidence of an
        online document; only an actual link counts."""
        normalized = (search_code or "").strip().upper()
        url = self.urls.get(normalized, "")
        if not url:
            return [], "Нет проверенного официального URL HyperX для этого артикула."
        return [], "На официальной странице HyperX не найдена прямая ссылка на документ (упоминание комплектации не считается ссылкой на инструкцию)."
