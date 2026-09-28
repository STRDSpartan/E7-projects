"""Accès aux données de référence (sets, alias de stats, héros)."""

from __future__ import annotations

import json
import unicodedata
from functools import cache
from pathlib import Path
from typing import Any

_REPO_REF = Path(__file__).resolve().parents[2] / "data" / "reference"
_PKG_REF = Path(__file__).resolve().parent / "_reference"


def reference_dir() -> Path:
    return _REPO_REF if _REPO_REF.is_dir() else _PKG_REF


@cache
def load(name: str) -> dict[str, Any]:
    with (reference_dir() / f"{name}.json").open(encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)
    data.pop("_comment", None)
    return data


def normalize(text: str) -> str:
    """Minuscules, sans accents, espaces compactés — pour comparer des sorties OCR."""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(stripped.casefold().replace("’", "'").split())


def set_pieces(set_name: str) -> int:
    return int(load("sets")[set_name]["pieces"])


def hero_names(lang: str = "fr") -> list[str]:
    return [h.get(lang) or h["fr"] for h in load("heroes")["heroes"]]


def artifact_info(name: str | None, score_cutoff: float = 80) -> dict[str, Any] | None:
    """Artefact du référentiel le plus proche d'un nom (FR ou EN, tolérant au bruit OCR)."""
    if not name:
        return None
    from rapidfuzz import fuzz, process

    arts = load("artifacts")["artifacts"]
    choices = {}
    for a in arts:
        for n in (a["fr"], a["en"]):
            choices[normalize(n).replace(" ", "")] = a
    match = process.extractOne(
        normalize(name).replace(" ", ""),
        list(choices),
        scorer=fuzz.ratio,
        score_cutoff=score_cutoff,
    )
    return dict(choices[match[0]]) if match else None


def hero_info(name: str) -> dict[str, Any] | None:
    key = normalize(name)
    for h in load("heroes")["heroes"]:
        if key in (normalize(h.get("en") or h["fr"]), normalize(h["fr"])):
            return dict(h)
    return None
