"""Conversion de lignes OCR ("Vitesse 18", "Chances de critique 12%") en StatLine.

Volontairement pur (aucune dépendance à la capture) : c'est ce module qui est
testé en premier quand on ajoute une langue ou qu'on corrige une erreur OCR.
"""

from __future__ import annotations

import re

from rapidfuzz import fuzz, process

from e7showcase.models.gear import StatLine
from e7showcase.models.stats import StatType
from e7showcase.reference import load, normalize

# Confusions OCR fréquentes dans les chiffres
_OCR_DIGIT_FIXES = str.maketrans({"O": "0", "o": "0", "l": "1", "I": "1", "S": "5", ",": "."})
# Valeur en fin de ligne, séparateurs de milliers tolérés (« 1 203 », « 18,540 »)
_VALUE_RE = re.compile(
    r"[+]?\s*([0-9OoIlS](?:[0-9OoIlS]|[ \u00a0\u202f.,](?=[0-9OoIlS]))*)\s*(%?)\s*$"
)
_THOUSANDS_RE = re.compile(r"^\d{1,3}(?:[ \u00a0\u202f.,]\d{3})+$")
_PCT_CAPABLE = {"atk": StatType.ATK_PCT, "hp": StatType.HP_PCT, "def": StatType.DEF_PCT}


class StatParseError(ValueError):
    pass


def _to_number(raw: str, pct: bool) -> float:
    digits = raw.translate(_OCR_DIGIT_FIXES)
    if not pct and _THOUSANDS_RE.match(digits):
        return float(re.sub(r"\D", "", digits))
    return float(re.sub(r"[ \u00a0\u202f]", "", digits))


def _aliases(lang: str) -> dict[str, str]:
    data = load("stat_aliases")
    merged = dict(data.get("en", {}))
    merged.update(data.get(lang, {}))
    return merged


def parse_stat_line(line: str, lang: str = "fr", score_cutoff: float = 80) -> StatLine:
    text = line.strip()
    m = _VALUE_RE.search(text)
    if not m:
        raise StatParseError(f"Aucune valeur trouvée dans {line!r}")
    raw_value, pct = m.group(1), m.group(2) == "%"
    value = _to_number(raw_value, pct)
    label = normalize(text[: m.start()]).rstrip(" +:")
    if not label:
        raise StatParseError(f"Aucun libellé trouvé dans {line!r}")

    aliases = _aliases(lang)
    key = aliases.get(label)
    if key is None:
        match = process.extractOne(
            label, aliases.keys(), scorer=fuzz.ratio, score_cutoff=score_cutoff
        )
        if match is None:
            raise StatParseError(f"Libellé inconnu {label!r} (ligne {line!r})")
        key = aliases[match[0]]

    stat = _PCT_CAPABLE[key] if key in _PCT_CAPABLE and pct else StatType(key)
    return StatLine(stat=stat, value=value)


def parse_stat_block(lines: list[str], lang: str = "fr") -> list[StatLine]:
    """Parse plusieurs lignes en ignorant celles qui ne sont pas des stats (titres, bruit)."""
    out: list[StatLine] = []
    for line in lines:
        try:
            out.append(parse_stat_line(line, lang))
        except StatParseError:
            continue
    return out
