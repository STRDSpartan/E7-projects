"""Blasons de référence des sets d'équipement (base de données Hideout Guides).

Sans blason connu, un set ne peut pas être reconnu sur la fiche d'un héros. Les icônes
publiques de https://www.hideoutgacha.com/games/epic-seven/database/equipment sont
téléchargées UNE fois dans la bibliothèque LOCALE de l'utilisateur (jamais dans le dépôt),
recadrées au plus juste comme un blason lu en jeu. Un blason appris sur une capture du
joueur reste prioritaire : il n'est jamais remplacé.

Mesuré sur captures réelles (720p → 4K) avec ces seules icônes : 18/18 pièces, bon set
≥ 0,93, meilleur mauvais set ≤ 0,66.
"""

from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import Any

from PIL import Image

from e7showcase.models.gear import GearSet

log = logging.getLogger(__name__)

BASE_URL = "https://www.hideoutgacha.com/images/epic-seven/database/equipment"
USER_AGENT = "e7showcase (vitrines de roster pour guildes ; outil communautaire)"

# code de l'icône sur le site → set
ICONS: dict[str, GearSet] = {
    "att": GearSet.ATTACK,
    "def": GearSet.DEFENSE,
    "max_hp": GearSet.HEALTH,
    "speed": GearSet.SPEED,
    "cri": GearSet.CRITICAL,
    "cri_dmg": GearSet.DESTRUCTION,
    "acc": GearSet.HIT,
    "res": GearSet.RESIST,
    "vampire": GearSet.LIFESTEAL,
    "counter": GearSet.COUNTER,
    "coop": GearSet.UNITY,
    "immune": GearSet.IMMUNITY,
    "rage": GearSet.RAGE,
    "penetrate": GearSet.PENETRATION,
    "scar": GearSet.INJURY,
    "shield": GearSet.PROTECTION,
    "torrent": GearSet.TORRENT,
    "revenge": GearSet.REVENGE,
    "opener": GearSet.WARFARE,
    "chase": GearSet.PURSUIT,
    "riposte": GearSet.RIPOSTE,
    "revenant": GearSet.REVERSAL,
    "weak": GearSet.WEAKENING,
    "might": GearSet.FERVOR,
}


def icon_to_shield(data: bytes) -> Image.Image:
    """Icône transparente → blason sur fond sombre, recadré comme en jeu."""
    from e7showcase.vision.set_catalog import tight_shield

    with Image.open(io.BytesIO(data)) as src:
        icon = src.convert("RGBA")
    background = Image.new("RGBA", icon.size, (0, 0, 0, 255))
    background.alpha_composite(icon)
    return tight_shield(background.convert("RGB"))


def missing(directory: Path) -> list[str]:
    return [code for code, s in ICONS.items() if not (directory / f"{s.value}.png").exists()]


def fetch_set_icons(directory: Path, client: Any = None) -> list[str]:
    """Télécharge les blasons manquants ; renvoie les sets ajoutés (erreurs réseau ignorées)."""
    todo = missing(directory)
    if not todo:
        return []
    own = client is None
    if own:
        import httpx

        client = httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=20)
    added: list[str] = []
    try:
        directory.mkdir(parents=True, exist_ok=True)
        for code in todo:
            try:
                response = client.get(f"{BASE_URL}/icon_set_{code}.png")
                response.raise_for_status()
                shield = icon_to_shield(response.content)
            except Exception as exc:  # noqa: BLE001 - hors ligne : on garde l'apprentissage
                log.warning("Blason du set %s indisponible : %s", code, exc)
                continue
            gear_set = ICONS[code]
            shield.save(directory / f"{gear_set.value}.png")
            added.append(gear_set.value)
    finally:
        if own:
            client.close()
    return added
