"""Régénère data/reference/heroes.json et artifacts.json depuis e7codex.com,
puis ajoute les effets des artefacts depuis e7gw.xyz/artifacts.

Uniquement des données factuelles (codes, noms, élément, classe, rareté, skins, chemins
d'images relatifs) : aucune image n'est téléchargée ni committée.

    python scripts/update_reference.py
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import httpx

from e7showcase.sources import e7gw
from e7showcase.sources.e7codex import USER_AGENT, build_artifacts, build_heroes, fetch_json

REF = Path(__file__).resolve().parents[1] / "data" / "reference"
SOURCE = (
    "Généré depuis e7codex.com (archive fan-made ; contenu du jeu © Smilegate / Super "
    "Creative) par scripts/update_reference.py le {date}. Effets des artefacts ('effect_en' : "
    "niveau de compétence 1 → 11, 'lore_en') : e7gw.xyz/artifacts. Ne pas éditer à la main."
)


def main() -> None:
    with httpx.Client(follow_redirects=True) as client:
        units = fetch_json(client, "data/units.json")
        artifacts = fetch_json(client, "data/artifacts.json")
        fr = fetch_json(client, "data/lang/fr.json")
        page = client.get(e7gw.URL, headers={"User-Agent": USER_AGENT}, timeout=60)
        page.raise_for_status()
    today = date.today().isoformat()
    heroes = build_heroes(units, fr)
    arts = build_artifacts(artifacts, fr)
    effects = e7gw.enrich(arts, e7gw.parse_artifacts(page.text))
    for name, key, items in (("heroes", "heroes", heroes), ("artifacts", "artifacts", arts)):
        payload = {"_comment": SOURCE.format(date=today), key: items}
        (REF / f"{name}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
        )
    skins = sum(len(h["skins"]) for h in heroes)
    print(f"{len(heroes)} héros ({skins} skins), {len(arts)} artefacts ({effects} effets) → {REF}")


if __name__ == "__main__":
    main()
