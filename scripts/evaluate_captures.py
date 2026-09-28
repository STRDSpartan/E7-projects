"""Mesure la précision du scanner sur un dossier LOCAL de captures + vérité terrain.

Le dossier (jamais committé : captures et roster réels) contient :
  - des captures « Infos de héros » ;
  - `sets-catalog*.<ext>` : captures du catalogue des sets (filtre d'inventaire) ;
  - `expected.json` : { "<fichier fiche>": {name, level, element, role, power, gear_score_avg,
    stats: {...}, gear: {slot: {score, level, enhance, set, main: [stat, valeur], subs: [...]}}} }

    python scripts/evaluate_captures.py <dossier> [profil]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from PIL import Image

from e7showcase.config import regions
from e7showcase.scanner.batch import learn_catalog
from e7showcase.scanner.hero_scanner import HeroScanner
from e7showcase.vision.ocr import OcrEngine, get_engine


def evaluate(
    caps: Path, profile: str = "auto", ocr: OcrEngine | None = None, verbose: bool = True
) -> tuple[int, int]:
    expected: dict[str, Any] = json.loads((caps / "expected.json").read_text(encoding="utf-8"))
    first = Image.open(caps / next(iter(expected)))
    scanner = HeroScanner(ocr or get_engine(), regions(profile, first.width / first.height))
    for catalog in sorted(caps.glob("sets-catalog*.*")):
        learned = learn_catalog(scanner, Image.open(catalog).convert("RGB"), None)
        if verbose:
            print(f"{catalog.name} : {len(learned)} sets appris")
    ok = total = 0

    def check(label: str, got: Any, want: Any) -> None:
        nonlocal ok, total
        total += 1
        ok += got == want
        if got != want and verbose:
            print(f"  ✗ {label}: lu={got!r} attendu={want!r}")

    for fname, exp in expected.items():
        hero = scanner.read_detail(Image.open(caps / fname).convert("RGB"))
        for k in ("name", "level", "element", "role", "power", "gear_score_avg"):
            check(f"{fname} {k}", getattr(hero, k), exp[k])
        for k, v in exp["stats"].items():
            check(f"{fname} stats.{k}", getattr(hero.stats, "defense" if k == "def" else k), v)
        for slot, g in exp["gear"].items():
            got = hero.gear.get(slot)
            if not got:
                check(f"{fname} {slot}", None, "pièce")
                continue
            for k in ("score", "level", "enhance"):
                check(f"{fname} {slot}.{k}", getattr(got, k), g[k])
            check(f"{fname} {slot}.set", got.set.value if got.set else None, g["set"])
            check(f"{fname} {slot}.main", [got.main.stat.value, got.main.value], g["main"])
            for i, s in enumerate(g["subs"]):
                sub = got.substats[i] if i < len(got.substats) else None
                check(f"{fname} {slot}.sub{i + 1}", [sub.stat.value, sub.value] if sub else None, s)
    return ok, total


if __name__ == "__main__":
    good, count = evaluate(Path(sys.argv[1]), sys.argv[2] if len(sys.argv) > 2 else "auto")
    print(f"PRÉCISION : {good}/{count} = {100 * good / count:.1f} %")
