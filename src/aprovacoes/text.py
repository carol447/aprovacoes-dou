from __future__ import annotations

import re
import unicodedata


def clean_space(value: object) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def key(value: object) -> str:
    text = clean_space(value).casefold()
    text = "".join(
        char for char in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(char)
    )
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def registry_key(value: object) -> str:
    text = clean_space(value).upper().replace("TCTC", "TC")
    digits = re.sub(r"\D", "", text).lstrip("0")
    return digits or "0" if re.search(r"\d", text) else ""


def preserve_tc_registry(value: object) -> str:
    text = clean_space(value).upper().replace("TCTC", "TC")
    match = re.search(r"TC\s*\d{3,}", text)
    return re.sub(r"\s+", "", match.group(0)) if match else ""
