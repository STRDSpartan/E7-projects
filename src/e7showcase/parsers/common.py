"""Petits parseurs de valeurs OCR, partagés par les lecteurs d'écran."""

from __future__ import annotations

import re

from e7showcase.reference import load, normalize

_FIXES = str.maketrans({"O": "0", "o": "0", "l": "1", "I": "1", "S": "5", "B": "8"})


def clean(text: str) -> str:
    """Espaces normalisés ; corrige « %6 » (texte lu retourné) en « 9% »."""
    t = " ".join(text.replace("　", " ").split())
    if m := re.fullmatch(r"%(\d+)", t):
        t = m.group(1)[::-1].translate(str.maketrans("69", "96")) + "%"
    return t


def parse_number(text: str) -> tuple[float, bool] | None:
    """« 2,835 » -> (2835, False) ; « 94.0% » -> (94.0, True) ; « +15 » -> (15, False)."""
    t = clean(text)
    pct = "%" in t
    digits = re.sub(r"[^0-9OolISB.,]", "", t).translate(_FIXES)
    if not digits:
        return None
    if re.fullmatch(r"\d{1,3}(,\d{3})+", digits) or (
        not pct and re.fullmatch(r"\d{1,3}(\.\d{3})+", digits)
    ):
        digits = re.sub(r"[.,]", "", digits)
    digits = digits.replace(",", ".").strip(".")
    try:
        return float(digits), pct
    except ValueError:
        return None


def parse_int(text: str, lo: int = 0, hi: int = 10**7) -> int | None:
    n = parse_number(text)
    if n is None or not (lo <= n[0] <= hi):
        return None
    return int(n[0])


def parse_level(text: str) -> int | None:
    t = normalize(text)
    if "max" in t:
        m = re.search(r"/\s*(\d{1,2})", t)
        return int(m.group(1)) if m else 60
    m = re.search(r"(\d{1,2})", t)
    return int(m.group(1)) if m else None


def parse_classes(text: str, lang: str = "fr") -> dict[str, str]:
    """« Glace Assassin Lion » -> {'element': 'ice', 'role': 'thief', 'zodiac': 'leo'}."""
    ref = load("classes")
    words = normalize(text)
    found: dict[str, str] = {}
    for kind in ("element", "role", "zodiac"):
        table = ref[kind].get(lang, {}) | ref[kind].get("en", {})
        for label, key in sorted(table.items(), key=lambda kv: -len(kv[0])):
            if re.search(rf"\b{re.escape(label)}\b", words):
                found[kind] = key
                break
    return found
