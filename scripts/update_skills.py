"""Régénère data/reference/skills.json : multiplicateurs de compétences de tous les héros.

Source : le calculateur de dégâts communautaire E7Calc (https://e7calc.xyz), code ouvert sous
licence ISC (https://github.com/tyopoyt/epic7-damage-calc). Son fichier de données
`heroes.ts` décrit chaque compétence par des fonctions (taux, puissance, pénétration...) :
elles sont exécutées dans Node avec des conditions neutres (aucun buff, cible sans effet)
pour obtenir les valeurs de base. Les bonus conditionnels sont seulement signalés
(`conditional`) ; aucun code tiers n'est embarqué dans l'application.

Recharges, textes et effets (soins, barrières, buffs, débuffs, jauge) : pages héros de la base
publique E7GW (https://e7gw.xyz/heroes, robots.txt : /hero autorisé), une requête toutes les
0,5 s ; `--cache DOSSIER` réutilise des pages déjà téléchargées.

    python scripts/update_skills.py [--cache DOSSIER]     # nécessite Node.js ≥ 22.6
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import time
from datetime import date
from pathlib import Path

import httpx

from e7showcase.sources import e7gw
from e7showcase.sources.e7codex import USER_AGENT

ROOT = Path(__file__).resolve().parents[1]
RAW = "https://raw.githubusercontent.com/tyopoyt/epic7-damage-calc/master/damage-calc/src/assets/data/"
HERE = Path(__file__).with_name("skills_extract")


def main() -> None:
    with httpx.Client(follow_redirects=True, timeout=60) as client:
        heroes = client.get(RAW + "heroes.ts").text
        constants = client.get(RAW + "constants.ts").text
    body = "\n".join(line for line in heroes.splitlines() if not line.startswith("import "))
    source = "\n".join(
        [
            (HERE / "stubs.ts").read_text(encoding="utf-8"),
            re.sub(r"^export ", "", constants, flags=re.M),
            re.sub(r"^export ", "", body, flags=re.M),
            (HERE / "extract.ts").read_text(encoding="utf-8"),
        ]
    )
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "run.ts"
        script.write_text(source, encoding="utf-8")
        result = subprocess.run(
            ["node", "--experimental-strip-types", "--no-warnings", str(script)],
            check=True,
            capture_output=True,
            text=True,
        )
    data = json.loads(result.stdout)
    cache = Path(sys.argv[sys.argv.index("--cache") + 1]) if "--cache" in sys.argv else None
    pages = []
    with httpx.Client(follow_redirects=True, timeout=60, headers={"User-Agent": USER_AGENT}) as c:
        for slug in e7gw.hero_slugs(c.get("https://e7gw.xyz/heroes").text):
            cached = cache / f"{slug}.html" if cache else None
            if cached and cached.is_file():
                page = cached.read_text(encoding="utf-8")
            else:
                page = c.get(e7gw.HERO_URL.format(slug=slug)).text
                time.sleep(0.5)
            pages.append(e7gw.parse_hero_page(page))
    heroes_done, effects = e7gw.merge_skills(data, pages)
    payload = {
        "_comment": (
            "Multiplicateurs de compétences (taux, puissance, amélioration, pénétration, "
            "bonus fixes) extraits du calculateur E7Calc (github.com/tyopoyt/epic7-damage-calc, "
            f"licence ISC) par scripts/update_skills.py le {date.today().isoformat()}. "
            "'conditional' : bonus conditionnels non appliqués par défaut. 'cooldown', 'passive', "
            "'effects' : pages héros d'E7GW (e7gw.xyz), analysées par parsers/skill_effects.py. "
            "Ne pas éditer à la main."
        ),
        "heroes": data,
    }
    target = ROOT / "data" / "reference" / "skills.json"
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(
        result.stderr.strip(),
        f"; effets E7GW : {heroes_done} héros, {effects} compétences",
        "→",
        target,
    )


if __name__ == "__main__":
    main()
