"""Effets des artefacts depuis la base publique E7GW (https://e7gw.xyz/artifacts).

La page liste chaque artefact avec son effet du niveau de compétence 1 au niveau maximum
(« 5% → 10% ») et son texte d'ambiance. Seul ce texte factuel est repris dans
data/reference/artifacts.json (par scripts/update_reference.py) ; aucune image.
Le robots.txt du site autorise /artifacts.
"""

from __future__ import annotations

import html
import re
import unicodedata
from typing import Any

URL = "https://e7gw.xyz/artifacts"

_CARD_RE = re.compile(
    r'<div class="artifact-card[^"]*"\s+id="([^"]+)"\s+data-name="[^"]*"\s+'
    r'data-class="([^"]*)"\s+data-rarity="(\d)">(.*?)</p>\s*</div>',
    re.S,
)
_NAME_RE = re.compile(r'<div class="truncate font-semibold"([^>]*)>([^<]+)</div>')
_EFFECT_SPLIT = '<p class="mt-2 text-xs leading-snug text-mut">'
# Noms différents entre E7GW et e7codex (clé normalisée E7GW → clé e7codex)
ALIASES = {"elegiaccandles": "elegiaccandle", "ascendingaxe": "axeofheavenlymandate"}


def key(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name.lower()).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", ascii_name)


def parse_artifacts(page: str) -> list[dict[str, Any]]:
    """Cartes de la page /artifacts : nom, classe, rareté, effet, texte d'ambiance."""
    cards: list[dict[str, Any]] = []
    for _gid, role, rarity, body in _CARD_RE.findall(page):
        name = _NAME_RE.search(body)
        if not name:
            continue
        lore = re.search(r'title="([^"]*)"', name.group(1))
        effect = html.unescape(re.sub(r"<[^>]+>", "", body.split(_EFFECT_SPLIT)[-1])).strip()
        cards.append(
            {
                "name": html.unescape(name.group(2)).strip(),
                "role": role,
                "rarity": int(rarity),
                "effect": None if effect.startswith("No effect") else effect.replace("..", "."),
                "lore": html.unescape(lore.group(1)) if lore else None,
            }
        )
    return cards


def enrich(artifacts: list[dict[str, Any]], cards: list[dict[str, Any]]) -> int:
    """Ajoute `effect_en` / `lore_en` aux artefacts du référentiel ; renvoie le nombre enrichi."""
    by_key = {key(a["en"]): a for a in artifacts if a.get("en")}
    done = 0
    for card in cards:
        art = by_key.get(ALIASES.get(key(card["name"]), key(card["name"])))
        if art is None:
            continue
        if card["effect"]:
            art["effect_en"] = card["effect"]
            done += 1
        if card["lore"]:
            art["lore_en"] = card["lore"]
    return done
