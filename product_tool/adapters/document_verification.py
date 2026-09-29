"""Content-based document verification: is this actually an instruction
manual for the expected model/variant, and what languages does it actually
contain? Declarations of conformity and certificates are excluded outright
and are never classified as instructions, regardless of model/code match.

This module operates on already-extracted text -- it does not fetch or
parse PDF bytes itself (see adapters/dns.py for the bounded fetch).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

REGULATORY_KEYWORDS = (
    r"declaration of conformity",
    r"декларац\w*\s+о?\s*соответств",
    r"сертификат\s+соответств",
    r"certificate of conformity",
    r"eac\s+declaration",
    r"технический\s+регламент",
)

LANGUAGE_MARKERS = {
    "ru": (r"\bинструкция\b", r"\bруководств\w*\s+пользовател", r"[а-яё]{5,}"),
    "en": (r"\buser manual\b", r"\binstruction", r"\bwarranty\b", r"\bmicrophone\b"),
    "uk": (r"\bінструкці", r"\bмікрофон\b"),
    "kk": (r"пайдаланушы\s+нұсқаулығы", r"құрылғы"),
    "de": (r"\bbedienungsanleitung\b", r"\bgebrauchsanweisung\b"),
    "fr": (r"\bmode d\W?emploi\b", r"\bguide d\W?utilisation\b"),
    "es": (r"\bmanual de usuario\b", r"\binstrucciones\b"),
}


@dataclass(frozen=True)
class DocumentVerification:
    accepted: bool
    # "instruction_manual" | "regulatory_excluded" | "model_mismatch" |
    # "conflicting_model_reference" | "unclassified"
    document_type: str
    matched_model: bool
    matched_code: bool
    languages: tuple[str, ...] = field(default_factory=tuple)
    reason: str = ""
    conflicting_reference_found: str = ""  # the specific conflicting token, if any


def is_regulatory_document(text: str) -> bool:
    return any(re.search(pattern, text, re.I) for pattern in REGULATORY_KEYWORDS)


def detect_languages(text: str) -> tuple[str, ...]:
    found = []
    for lang, patterns in LANGUAGE_MARKERS.items():
        if any(re.search(p, text, re.I) for p in patterns):
            found.append(lang)
    return tuple(sorted(found))


def verify_document(
    text: str,
    *,
    expected_model_tokens: list[str],
    expected_code: str = "",
    conflicting_model_tokens: list[str] = (),
    conflicting_codes: list[str] = (),
) -> DocumentVerification:
    """Verify that `text` is an instruction manual for the expected model.

    A similar-sounding filename or dealer label is never sufficient --
    the actual extracted text must contain the model name (or the exact
    manufacturer/seller code) before this is accepted as a match.
    Regulatory documents (declarations, certificates) are excluded
    outright, even if they happen to mention the right model.

    A model/code match is accepted ONLY when the text contains no
    explicitly-known CONFLICTING model name or code (Stage 11.5): a
    document can legitimately mention the expected code in passing (e.g.
    a compatibility/cross-reference table) while actually being the manual
    for a different, named sibling model -- that must still be rejected,
    not accepted just because the code happened to appear somewhere.
    `conflicting_model_tokens`/`conflicting_codes` are optional and empty
    by default (no known siblings to check against); callers that know a
    brand's other model names/codes should pass them explicitly.
    """
    if not text or not text.strip():
        return DocumentVerification(
            accepted=False, document_type="unclassified",
            matched_model=False, matched_code=False,
            reason="Empty or unreadable document text.",
        )

    if is_regulatory_document(text):
        return DocumentVerification(
            accepted=False, document_type="regulatory_excluded",
            matched_model=False, matched_code=False,
            languages=detect_languages(text),
            reason=(
                "Document identifies itself as a declaration of conformity / certificate. "
                "Regulatory documents are never treated as instructions or card material, "
                "regardless of model/code match."
            ),
        )

    matched_model = any(
        re.search(re.escape(token), text, re.I) for token in expected_model_tokens if token
    )
    matched_code = bool(expected_code) and re.search(re.escape(expected_code), text, re.I) is not None
    languages = detect_languages(text)

    conflicting_token = next(
        (tok for tok in conflicting_model_tokens if tok and re.search(re.escape(tok), text, re.I)),
        None,
    ) or next(
        (code for code in conflicting_codes if code and code != expected_code and re.search(re.escape(code), text, re.I)),
        None,
    )
    if conflicting_token and (matched_model or matched_code):
        return DocumentVerification(
            accepted=False, document_type="conflicting_model_reference",
            matched_model=matched_model, matched_code=matched_code, languages=languages,
            conflicting_reference_found=conflicting_token,
            reason=(
                f"The expected model/code was found, but so was a known CONFLICTING "
                f"model/code reference ({conflicting_token!r}) -- the document may only "
                f"mention the expected product in passing (e.g. a compatibility table) "
                f"while actually covering a different sibling model. A match alone is not "
                f"accepted when a contradiction is present -- rejected."
            ),
        )

    if not matched_model and not matched_code:
        return DocumentVerification(
            accepted=False, document_type="model_mismatch",
            matched_model=False, matched_code=False, languages=languages,
            reason=(
                "Neither the expected model name nor the expected manufacturer/seller code "
                "was found anywhere in the document's own text. A similar filename or dealer "
                "label is not sufficient identity confirmation -- rejected."
            ),
        )

    return DocumentVerification(
        accepted=True, document_type="instruction_manual",
        matched_model=matched_model, matched_code=matched_code, languages=languages,
        reason="Expected model name and/or manufacturer code confirmed in the document's own text, with no conflicting reference found.",
    )
