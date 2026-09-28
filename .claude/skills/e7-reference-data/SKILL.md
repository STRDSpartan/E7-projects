---
name: e7-reference-data
description: Ajouter ou mettre à jour les données de référence d'Epic Seven (héros, sets, libellés de stats par langue) dans data/reference/*.json, utilisées pour le fuzzy-matching OCR et l'affichage. À utiliser après la sortie d'un nouveau héros ou set, ou pour ajouter une langue de client.
---

# Données de référence

**Héros et artefacts sont générés** depuis e7codex.com : `python scripts/update_reference.py`
(390 héros, skins, 282 artefacts, noms FR/EN, chemins d'images). Ne pas éditer
`heroes.json` / `artifacts.json` à la main : corriger le générateur
(`src/e7showcase/sources/e7codex.py`) et relancer. Les sets et libellés de stats restent manuels.

Fichiers : `data/reference/heroes.json`, `sets.json`, `stat_aliases.json`
(chargés par `src/e7showcase/reference.py`, mis en cache).

## Ajouter des héros
Entrée : `{"code": "c1234", "en": "Name", "fr": "Nom", "element": "fire|ice|earth|light|dark",
"role": "knight|warrior|thief|ranger|mage|soul-weaver", "stars": 3|4|5}`.
- Source publique vérifiable (wiki communautaire, datamine publique) ; citer la source dans le commit.
- Les noms FR doivent être **exactement** ceux du client (accents, apostrophes typographiques) :
  c'est la cible du fuzzy-matching.
- Variantes (« Ravi » vs « Ravi de l'apocalypse ») : vérifier qu'un nom OCR partiel ne matche pas
  la mauvaise variante → ajouter un test dans `tests/test_hero_parser.py`.

## Ajouter un set
Ajouter la valeur dans `models/gear.py::GearSet`, puis dans `sets.json` avec `pieces`, `fr`, `en`,
`verified`. Si le set est utilisé par Fribbels, vérifier le nom `XxxSet` dans l'importeur.

## Ajouter une langue
1. `stat_aliases.json` : nouvelle section, clés **normalisées** (`reference.normalize` :
   minuscules, sans accents, espaces simples).
2. Ajouter le champ de langue dans `heroes.json` et `sets.json`.
3. Tests paramétrés dans `tests/test_stat_parser.py` avec de vraies lignes du client.

## Vérification
`pytest` puis la skill `dev-checks`. Ne jamais committer d'images/icônes du jeu.
