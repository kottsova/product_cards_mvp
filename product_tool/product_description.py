"""Presentation filter for product overviews; source HTML/evidence remains intact."""
from __future__ import annotations

import re

_HELP_HEADING = re.compile(
    r"^(?:вопросы и ответы|"
    r"часто задаваемые вопросы|FAQ|"
    r"помощь и поддержка|"
    r"устранение неполадок|"
    r"troubleshooting|support and help)$",
    re.I,
)
_HELP_LINE = re.compile(
    r"(?:^как\s+(?:зарегистрировать|"
    r"установить|"
    r"настроить|"
    r"подключить)\b|"
    r"обратитесь к странице|"
    r"настройка роутера|"
    r"^шаг\s*\d+|^\d+[.)]\s+)",
    re.I,
)


def product_description(text: str) -> str:
    """Drop help/FAQ blocks and procedures while retaining product features."""
    kept = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        if _HELP_HEADING.fullmatch(line):
            break
        if _HELP_LINE.search(line):
            continue
        kept.append(line)
    return "\n".join(kept)
