from __future__ import annotations

import re

_SPACE_RE = re.compile(r"\s+")
_DUPLICATE_CITY_RE = re.compile(r"^(?:г\.)?город\s+москва", re.IGNORECASE)


def normalize_address(address: str) -> str:
    """Apply conservative, auditable cleanup without changing house identifiers."""

    value = address.replace("ё", "е").replace("Ё", "Е").strip()
    value = _DUPLICATE_CITY_RE.sub("Москва", value)
    value = re.sub(r"^г\.\s*Москва", "Москва", value, flags=re.IGNORECASE)
    value = re.sub(r"\s*,\s*", ", ", value)
    value = re.sub(r"\s+([./])\s+", r"\1", value)
    value = _SPACE_RE.sub(" ", value)
    return value.strip(" ,")
