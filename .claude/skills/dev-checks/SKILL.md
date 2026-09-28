---
name: dev-checks
description: Définition de « terminé » du projet E7 Showcase - installer l'environnement de dev puis lancer ruff (lint + format), mypy strict et pytest, et rapporter les résultats exacts. À exécuter à la fin de toute modification de code, avant commit.
---

# Vérifications de développement

## Installation (une fois)
```bash
python -m venv .venv && . .venv/bin/activate      # Windows : .venv\Scripts\activate
pip install -e ".[dev]"                           # + [scan] [render] [bot] selon le besoin
```

## À lancer, dans cet ordre
```bash
ruff format .
ruff check .
mypy
pytest
```
Tout doit être vert. En cas d'échec : corriger la cause, jamais désactiver un test, ajouter un
`# type: ignore` ou un `noqa` sans justification commentée.

## Rapport
Indiquer pour chaque commande : ✅/❌ et, en cas d'échec, les lignes d'erreur pertinentes.
Signaler explicitement les vérifications non exécutées (ex. rendu PNG sans navigateur, OCR
sans extra `[scan]`, capture réelle impossible hors Windows).
