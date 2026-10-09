"""Measured image metadata for a saved photo URL; never infer pixels from HTML hints."""
from __future__ import annotations

import struct
from pathlib import Path
from urllib.parse import urlsplit

import requests

from .adapters.lg_documents import BinarySafeSession
from .adapters.policy_session import PolicyAwareSession, RequestBudget, request_budget

MAX_IMAGE_BYTES = 8_000_000
ALLOWED_BY_SOURCE = {
    'razer_model': ('razer.com','razerzone.com'),
    'razer_configuration': ('razer.com','razerzone.com'),
    'xbox_hardware': ('microsoft.com','xboxservices.com','xbox.com','img-prod-cms-rt-microsoft-com.akamaized.net'),
    'xbox_configuration': ('microsoft.com','xboxservices.com','xbox.com','img-prod-cms-rt-microsoft-com.akamaized.net'),
    "playstation": ("playstation.com",),
    "playstation_model": ("playstation.com",),
    "playstation_hardware": ("playstation.com",),
    "apple": ("cdn-apple.com", "apple.com"),
    "apple_model": ("cdn-apple.com", "apple.com"),
    "jbl": ("jbl.com",),
    "lg": ("lg.com", "lge.com"),
    "lg_kz": ("lg.com", "lge.com"),
    "lg_ru": ("lg.com", "lge.com"),
    "lg_global": ("lg.com", "lge.com"),
    "sulpak": ("sulpak.kz",),
    "samsung": ("samsung.com", "samsungimages.com"),
    "bosch_home": ("bosch-home.com", "bosch-home.kz", "bsh-group.com"),
    "lenovo_psref": ("psrefstuff.lenovo.com", "psref.lenovo.com", "download.lenovo.com", "static.pub"),
    "lenovo_support": ("lenovo.com", "static.pub"),
}


def log_name(source_key: str) -> str:
    if source_key in {"lg", "lg_kz", "lg_ru", "lg_global", "sulpak"}:
        return "lg_fetch_log.json"
    return f"{source_key}_fetch_log.json"


def format_file_size(size: int | None) -> str:
    if size is None:
        return "не определено"
    if size >= 1_048_576:
        return f"{size / 1_048_576:.1f} MB"
    if size >= 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size} B"


def image_dimensions(data: bytes) -> tuple[int, int, str] | None:
    """Decode only image headers; reject incomplete or implausible dimensions."""
    result = None
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
        result = (*struct.unpack(">II", data[16:24]), "PNG")
    elif data[:2] == b"\xff\xd8":
        pos = 2
        while pos + 4 <= len(data):
            if data[pos] != 0xff:
                break
            marker = data[pos + 1]
            pos += 2
            if marker in (0xd8, 0xd9) or 0xd0 <= marker <= 0xd7:
                continue
            if pos + 2 > len(data):
                break
            length = int.from_bytes(data[pos:pos + 2], "big")
            if length < 2 or pos + length > len(data):
                break
            if marker in (0xc0, 0xc1, 0xc2, 0xc3, 0xc5, 0xc6, 0xc7, 0xc9, 0xca, 0xcb, 0xcd, 0xce, 0xcf) and length >= 7:
                result = (int.from_bytes(data[pos + 5:pos + 7], "big"),
                          int.from_bytes(data[pos + 3:pos + 5], "big"), "JPG")
                break
            pos += length
    elif data[:4] == b"RIFF" and data[8:12] == b"WEBP" and len(data) >= 30:
        kind = data[12:16]
        if kind == b"VP8X":
            result = (1 + int.from_bytes(data[24:27], "little"),
                      1 + int.from_bytes(data[27:30], "little"), "WEBP")
        elif kind == b"VP8L" and data[20:21] == b"\x2f":
            bits = int.from_bytes(data[21:25], "little")
            result = ((bits & 0x3fff) + 1, ((bits >> 14) & 0x3fff) + 1, "WEBP")
        elif kind == b"VP8 " and data[23:26] == b"\x9d\x01\x2a":
            result = (int.from_bytes(data[26:28], "little") & 0x3fff,
                      int.from_bytes(data[28:30], "little") & 0x3fff, "WEBP")
    if result and 0 < result[0] <= 100_000 and 0 < result[1] <= 100_000:
        return result
    return None


def inspect_saved_photo(url: str, source_key: str, log_path: Path, *, underlying=None) -> dict[str, int | str]:
    """One bounded policy-aware GET of an already saved image; no discovery."""
    allowed = ALLOWED_BY_SOURCE.get(source_key, ())
    host = (urlsplit(url).hostname or "").casefold()
    if urlsplit(url).scheme != "https" or not any(host == h or host.endswith("." + h) for h in allowed):
        raise ValueError("Image host is not approved for this saved source.")
    transport = BinarySafeSession(underlying if underlying is not None else requests.Session())
    session = PolicyAwareSession(Path(log_path), allowed_hosts=allowed, underlying=transport,
                                 max_bytes=MAX_IMAGE_BYTES)
    budget = RequestBudget(max_per_row=1, max_total=1)
    budget.begin_row(source_key)
    with request_budget(budget):
        response = session.get(url, timeout=10)
    if not response.ok or response.marker:
        raise ValueError("Image access stopped by the current source policy.")
    if response.truncated:
        raise ValueError("Image exceeds the 8 MB measurement limit.")
    data = response.text.encode("latin-1")
    dimensions = image_dimensions(data)
    if not dimensions:
        raise ValueError("Image bytes do not contain a supported PNG, JPG or WEBP header.")
    width, height, image_format = dimensions
    return {"width": width, "height": height, "size_bytes": len(data), "format": image_format}
