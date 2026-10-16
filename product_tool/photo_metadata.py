"""Measured image metadata for a saved photo URL; never infer pixels from HTML hints."""
from __future__ import annotations

from io import BytesIO
import struct
from pathlib import Path
from urllib.parse import urlsplit

import requests

from .adapters.lg_documents import BinarySafeSession
from .adapters.policy_session import PolicyAwareSession, RequestBudget, request_budget
from .job_progress import observed

MAX_IMAGE_BYTES = 8_000_000
ALLOWED_BY_SOURCE = {
    'dreame_model': ('dreametech.com','dreame.tech','cdn.shopify.com'),
    'electrolux': ('electrolux.co.uk','electrolux.ie','electrolux.se','electrolux.de','electrolux.pl','electrolux.bynder.com'),
    'xiaomi_model': ('appmifile.com',),
    'hyperx': ('hyperx.com',),
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


@observed('extraction_photos')
def inspect_saved_photo(url: str, source_key: str, log_path: Path, *, underlying=None,
                        full_verification=False, save_dir: Path | None=None) -> dict[str, int | str]:
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
    content_type=next((v for k,v in response.headers.items() if k.casefold()=='content-type'),'').split(';',1)[0].strip().lower()
    binary_image=content_type=='application/octet-stream' and (full_verification or source_key in {'hyperx','xiaomi_model','dreame_model','electrolux'})
    extra_types={'image/gif','image/avif','image/tiff','image/bmp'} if full_verification else set()
    if content_type not in {'image/png','image/jpeg','image/webp'}|extra_types and not binary_image:
        raise ValueError('Image response has an unsupported content-type.')
    dimensions = image_dimensions(data)
    if not dimensions and full_verification:
        from PIL import Image
        try:
            with Image.open(BytesIO(data)) as decoded:
                if decoded.format in {'GIF','AVIF','TIFF','BMP'}:dimensions=(*decoded.size,decoded.format)
        except Exception:pass
    if not dimensions:
        raise ValueError("Image bytes do not contain a supported PNG, JPG or WEBP header.")
    width, height, image_format = dimensions
    if not full_verification and source_key not in {'hyperx','xiaomi_model','dreame_model','electrolux'}:
        return {"width":width,"height":height,"size_bytes":len(data),"format":image_format}
    from PIL import Image
    try:
        with Image.open(BytesIO(data)) as decoded:
            decoded.verify()
            supported={'PNG','JPEG','WEBP'}|({'GIF','AVIF','TIFF','BMP'} if full_verification else set())
            if decoded.size!=(width,height) or decoded.format not in supported:raise ValueError('Image header/content mismatch')
        with Image.open(BytesIO(data)) as decoded:
            decoded.load()
            samples={0}
            if full_verification and getattr(decoded,'n_frames',1)>1:samples.update({decoded.n_frames//2,decoded.n_frames-1})
            blank=True
            for frame in sorted(samples):
                decoded.seek(frame);decoded.load();extrema=decoded.convert('RGB').getextrema()
                transparent=decoded.mode=='RGBA' and decoded.getchannel('A').getextrema()[1]==0
                if not transparent and any(lo!=hi for lo,hi in extrema):blank=False
            if blank:raise ValueError('Blank or transparent placeholder image')
    except Exception as exc:
        raise ValueError('Image bytes failed decoding verification.') from exc
    if width<64 or height<64:
        raise ValueError('Image is too small to be a product render.')
    effective_type={'PNG':'image/png','JPG':'image/jpeg','WEBP':'image/webp','GIF':'image/gif','AVIF':'image/avif','TIFF':'image/tiff','BMP':'image/bmp'}[image_format]
    if effective_type!=content_type and not binary_image:
        raise ValueError('Image format/content-type mismatch.')
    import hashlib
    measured={"width": width, "height": height, "size_bytes": len(data), "format": image_format, "content_type":content_type,"effective_content_type":effective_type,"sha256":hashlib.sha256(data).hexdigest()}
    if save_dir is not None:
        destination=Path(save_dir);destination.mkdir(parents=True,exist_ok=True)
        file=destination/(measured['sha256']+'.img')
        if not file.exists():file.write_bytes(data)
        measured['saved_file']=str(file)
    return measured
