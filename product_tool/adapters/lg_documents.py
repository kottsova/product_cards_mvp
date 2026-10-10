"""Stage 22: LG documents through the policy-aware session -- byte-safe fetch and content-based assessment.

The policy-aware client decodes every body as text. A PDF decoded as latin-1 is lossless (one character per byte), so a
wrapper that marks document responses as latin-1 lets `PolicyResponse.text.encode("latin-1")` give the original bytes back
without a second client and without leaving the policy path (allowlist, redirect check, host stop, budget, log).

A document goes through three separate states, never merged: a candidate LINK (an href printed on an official support page),
a reachable FILE (complete bytes that start with %PDF-), an INSTRUCTION confirmed by CONTENT (assess_document). The language of an
instruction is read from the extracted text only -- never from a file name, a URL or the label printed next to the link.
"""
from __future__ import annotations

import re

_BINARY_TYPES = ("application/pdf", "application/octet-stream", "application/x-pdf", "image/png", "image/jpeg", "image/webp")


class BinarySafeSession:
    """Wraps a requests-style session; a response whose content type is a document is decoded as latin-1."""

    def __init__(self, underlying):
        self.underlying = underlying

    @property
    def headers(self):
        return self.underlying.headers

    def get(self, url, **kwargs):
        response = self.underlying.get(url, **kwargs)
        headers = getattr(response, "headers", None) or {}
        content_type = str(headers.get("content-type", headers.get("Content-Type", ""))).casefold()
        if any(kind in content_type for kind in _BINARY_TYPES) or url.split("?", 1)[0].casefold().endswith(".pdf"):
            try:
                response.encoding = "latin-1"
            except AttributeError:
                pass
        return response


def document_bytes(response) -> bytes:
    """The body of a response that went through BinarySafeSession, as bytes."""
    return response.text.encode("latin-1", errors="replace")


def looks_like_pdf(data: bytes) -> bool:
    return data[:5] == b"%PDF-"


_KK_ONLY = set("әғқңөұүһӘҒҚҢӨҰҮҺ")
_UK_ONLY = set("їєґЇЄҐ")
_RU_WORDS = frozenset("и в не на с для что при или по из к от это как а но также если то все всех может можно должен перед после только".split())
_EN_WORDS = frozenset("the and of to for is are not with or this that before after only may can your from be use".split())
MIN_CHUNK_LETTERS = 120        # a chunk with fewer letters (a heading, a caption) is not classified
CHUNK_CHARS = 600
MIN_LANGUAGE_LETTERS = 500     # a language "is present" only with this many classified letters
RU_INSTRUCTION_LETTERS = 2500  # Russian INSTRUCTION text, not a legal notice repeated in ten languages: enough Russian text ...
RU_INSTRUCTION_MARKERS = 2     # ... and this many instruction words in it

_INSTRUCTION_MARKERS = ("руководств", "инструкц", "меры предосторожности", "безопасност", "перед использованием", "эксплуатац", "внимательно прочит", "owner's manual", "user manual",
                        "please read this manual", "user guide", "quick start guide", "safety instructions", "installing", "нұсқау", "қауіпсіздік")
_RU_INSTRUCTION_WORDS = ("руководств", "инструкц", "безопасност", "перед использованием", "эксплуатац", "внимательно прочит", "меры предосторожности", "подключ", "нажмите", "не допускайте")
_REGULATORY_HEADING = re.compile(r"декларац\w*\s+о?\s*соответств|declaration of conformity|сертификат\s+соответств|certificate of conformity|заявление о соответствии", re.I)


def _chunks(text: str) -> list[str]:
    """Runs of about CHUNK_CHARS characters cut at line ends, so a page that mixes languages is classified section by section."""
    chunks, current = [], ""
    for line in text.splitlines():
        current += line + "\n"
        if len(current) >= CHUNK_CHARS:
            chunks.append(current)
            current = ""
    if current.strip():
        chunks.append(current)
    return chunks


def chunk_language(text: str) -> str:
    """'ru' | 'kk' | 'uk' | 'en' | '' (too short or undecided) for one chunk of extracted text."""
    letters = [c for c in text if c.isalpha()]
    if len(letters) < MIN_CHUNK_LETTERS:
        return ""
    cyrillic = sum(1 for c in letters if "Ѐ" <= c <= "ӿ")
    latin = sum(1 for c in letters if c.isascii())
    words = re.findall(r"[^\W\d_]+", text.casefold())
    if cyrillic >= 0.6 * len(letters):
        if sum(1 for c in letters if c in _KK_ONLY) >= 0.01 * cyrillic:
            return "kk"
        if any(c in _UK_ONLY for c in letters):
            return "uk"
        return "ru" if sum(1 for w in words if w in _RU_WORDS) >= 0.06 * max(len(words), 1) else ""
    if latin >= 0.8 * len(letters):
        return "en" if sum(1 for w in words if w in _EN_WORDS) >= 0.06 * max(len(words), 1) else ""
    return ""


def document_languages(pages: list[str]) -> dict:
    """Letters per language, classified chunk by chunk over the extracted text (never from a name, URL or label).

    `present` = languages with at least MIN_LANGUAGE_LETTERS classified letters. `russian_instruction` is stricter than `present` on purpose: a leaflet
    prints its legal notice in Russian next to ten other languages while the guide itself is in English; only an amount of Russian text that carries
    instruction wording counts as a Russian instruction."""
    letters: dict[str, int] = {}
    russian_text: list[str] = []
    for page in pages:
        for chunk in _chunks(page):
            language = chunk_language(chunk)
            if language:
                letters[language] = letters.get(language, 0) + sum(1 for c in chunk if c.isalpha())
                if language == "ru":
                    russian_text.append(chunk.casefold())
    joined = " ".join(russian_text)
    ru_markers = sum(1 for word in _RU_INSTRUCTION_WORDS if word in joined)
    present = sorted(lang for lang, n in letters.items() if n >= MIN_LANGUAGE_LETTERS)
    return {"pages": len(pages), "letters_by_language": dict(sorted(letters.items())), "present": present, "russian_present": "ru" in present,
            "russian_instruction_markers": ru_markers, "russian_instruction": letters.get("ru", 0) >= RU_INSTRUCTION_LETTERS and ru_markers >= RU_INSTRUCTION_MARKERS}


def assess_document(pages: list[str], expected_tokens: list[str]) -> dict:
    """What the CONTENT says. regulatory = a conformity declaration/certificate heading at the head of the document and hardly any instruction wording
    (an instruction that merely contains a compliance notice is not regulatory); names_model = an expected model/code appears in the text."""
    text = "\n".join(pages)
    lowered = text.casefold()
    head = pages[0][:400] if pages else ""
    markers = sorted(m for m in _INSTRUCTION_MARKERS if m in lowered)
    regulatory = bool(_REGULATORY_HEADING.search(head)) and len(markers) < 3
    names_model = [t for t in expected_tokens if t and re.search(re.escape(t), text, re.I)]
    masks = [] if names_model else family_masks(text, expected_tokens)
    evidence = "exact" if names_model else "family_mask" if masks else "none"
    languages = document_languages(pages)
    instruction = bool(text.strip()) and not regulatory and len(markers) >= 2
    accepted = instruction and evidence != "none"
    other = conflicting_models(text, expected_tokens) if evidence == "none" else []
    kind = ("regulatory_excluded" if regulatory else "instruction_confirmed" if accepted else "instruction_conflicting_model" if instruction and other else
            "instruction_model_not_named" if instruction else "not_confirmed")
    return {"accepted": accepted, "kind": kind, "regulatory": regulatory, "names_model": names_model, "model_masks": masks, "model_evidence": evidence, "conflicting_models": other,
            "instruction_markers": markers, "languages": languages, "text_chars": len(text)}


def _fixed(token: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", token.rstrip("*").upper())


def conflicting_models(text: str, expected_tokens: list[str]) -> list[str]:
    """A model-like token (it has a digit, at least 5 fixed characters) that begins like an expected model (the first 4 characters) but is neither a beginning of it nor
    continues it: the document is about a sibling, not about this model. Only asked when the text names neither the model nor its family."""
    wanted = [_fixed(t) for t in expected_tokens if t]
    found = []
    for token in dict.fromkeys(re.findall(r"[A-Za-z0-9][A-Za-z0-9.\-]{4,}\**", text)):
        fixed = _fixed(token)
        if len(fixed) < 5 or not re.search(r"\d", fixed):
            continue
        for model in wanted:
            if len(model) >= 4 and fixed[:4] == model[:4] and not model.startswith(fixed) and not fixed.startswith(model):
                found.append(token)
                break
    return found[:5]


_MASK = re.compile(r"[A-Za-z0-9][A-Za-z0-9.\-]*\*+")
MIN_MASK_PREFIX = 4


def family_masks(text: str, expected_tokens: list[str]) -> list[str]:
    """LG manuals cover a model FAMILY and print it with a mask ("F2J3WS**", "65UT80*"). A mask whose fixed part (at least MIN_MASK_PREFIX letters/digits) is the
    beginning of an expected model names that model's family in the document's own text; it is weaker than the model itself and is reported as such."""
    wanted = [re.sub(r"[^A-Z0-9]", "", t.upper()) for t in expected_tokens if t]
    found = []
    for token in dict.fromkeys(_MASK.findall(text)):
        fixed = re.sub(r"[^A-Z0-9]", "", token.rstrip("*").upper())
        if len(fixed) >= MIN_MASK_PREFIX and any(model.startswith(fixed) for model in wanted):
            found.append(token)
    return found[:5]
