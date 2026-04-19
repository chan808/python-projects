from __future__ import annotations

import re
from typing import Optional


def normalize_brand_name(raw_brand_name: str, aliases: Optional[dict[str, str]] = None) -> str:
    cleaned = raw_brand_name.strip().lower()
    if aliases and cleaned in aliases:
        return aliases[cleaned]

    cleaned = re.sub(r"\s+", "", cleaned)
    cleaned = re.sub(r"[^a-z0-9_-]", "", cleaned)
    return cleaned
