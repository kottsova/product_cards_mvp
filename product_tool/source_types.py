"""Classifies a source_key as official or dealer, for provenance reporting.

This does not change attribute-resolution priority (see resolution.py) --
it only labels sources for display/export/provenance purposes. Official
priority and dealer-fallback-only-fills-empty-fields behavior already fall
out of resolve_attributes()'s existing per-attribute logic: a source_key
outside OFFICIAL/SUPPLIERS only ever reaches the unconfirmed single-source
branch, which never overwrites an official or supplier-confirmed value.
"""
from __future__ import annotations

OFFICIAL_SOURCE_KEYS = frozenset({"lg", "lg_kz", "lg_ru", "hyperx", "bosch_home"})

# All dealer/retailer fallback sources, including the trusted LG-only
# full-SKU supplier (sulpak), the general-purpose, all-brand
# supplementation fallback (dns -- fills missing characteristics/photos/
# instructions), and technopark (Stage 11.5 user preference: reserved for
# cross-checking disputed characteristics/variant identity against the
# official source, once an exact, verified URL exists -- no adapter has
# been built yet, since none does). Being in this set does not grant any
# special resolution trust by itself -- resolution.py's SUPPLIERS set is
# what grants sulpak its full_sku confirmation tier; dns/technopark
# are deliberately not members of SUPPLIERS, so a lone fact from either is
# never silently confirmed.
DEALER_SOURCE_KEYS = frozenset({"sulpak", "dns", "technopark"})


def source_type(source_key: str) -> str:
    """Returns 'official', 'dealer', or 'unknown' for a given source_key."""
    key = (source_key or "").strip().casefold()
    if key in OFFICIAL_SOURCE_KEYS:
        return "official"
    if key in DEALER_SOURCE_KEYS:
        return "dealer"
    return "unknown"
