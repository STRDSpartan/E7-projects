"""Régénère data/reference/skills.json : multiplicateurs de compétences de tous les héros.

Source : le calculateur de dégâts communautaire E7Calc (https://e7calc.xyz), code ouvert sous
licence ISC (https://github.com/tyopoyt/epic7-damage-calc). Son fichier de données
`heroes.ts` décrit chaque compétence par des fonctions (taux, puissance, pénétration...) :
elles sont exécutées dans Node avec des conditions neutres (aucun buff, cible sans effet)
pour obtenir les valeurs de base. Les bonus conditionnels sont seulement signalés
(`conditional`) ; aucun code tiers n'est embarqué dans l'application.

    python scripts/update_skills.py        # nécessite Node.js ≥ 22.6
"""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
from datetime import date
from pathlib import Path

import httpx

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
    payload = {
        "_comment": (
            "Multiplicateurs de compétences (taux, puissance, amélioration, pénétration, "
            "bonus fixes) extraits du calculateur E7Calc (github.com/tyopoyt/epic7-damage-calc, "
            f"licence ISC) par scripts/update_skills.py le {date.today().isoformat()}. "
            "'conditional' : bonus conditionnels non appliqués par défaut. Ne pas éditer à la main."
        ),
        "heroes": data,
    }
    target = ROOT / "data" / "reference" / "skills.json"
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(result.stderr.strip(), "→", target)


if __name__ == "__main__":
    main()
