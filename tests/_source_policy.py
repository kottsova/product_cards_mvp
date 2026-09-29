"""Generic "a source outside the approved list is never used" checks.

Tests state this rule as data (an approved list) instead of naming any
individual excluded source. `APPROVED_SOURCE_IDS` mirrors the executable
source registry (`product_tool/config/source_catalog.v2.json`); adding a
source to the product means adding it here deliberately, in review.
"""
from __future__ import annotations

from urllib.parse import urlsplit

APPROVED_SOURCE_IDS = frozenset({
    "lg_kz", "lg_ru", "sulpak", "bosch_home", "bosch_tools", "xiaomi_global",
    "samsung_kz", "apple_kz", "huawei_kz", "lenovo_kz", "lenovo_support_kz",
    "gigabyte_global",
})


def unapproved_source_ids(source_ids) -> set[str]:
    """Source ids present in a registry/catalog that are not on the approved list."""
    return set(source_ids) - APPROVED_SOURCE_IDS


def host_allowed(host: str, allowed_hosts) -> bool:
    host = (host or "").lower()
    return any(host == a or host.endswith("." + a) for a in (h.lower() for h in allowed_hosts))


def hosts_outside_allowlist(urls, allowed_hosts) -> set[str]:
    """Hosts of `urls` that are neither an allowed host nor its subdomain."""
    hosts = {(urlsplit(url).hostname or "").lower() for url in urls}
    return {host for host in hosts if not host_allowed(host, allowed_hosts)}
