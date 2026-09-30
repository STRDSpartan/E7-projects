# Scan : fonctionnement, calibration et extension

## Écrans utilisés
| Écran | Reconnu par | Sert à |
|---|---|---|
| **Infos de héros** (bouton sous les bottes) | titre « Infos de héros » | tout le héros : stats, 6 pièces, scores, artefact, empreinte, puissance |
| **Catalogue des sets** (filtre de l'inventaire) | lignes « Set Xxx » | blasons des 24 sets → bibliothèque locale (une fois pour toutes) |
| **Liste des héros** | boutons « Gérer l'équipement / Tout équiper » | navigation (mode assisté) ; nom + sets actifs ; **blasons des sets actifs** (nom et blason côte à côte) |

Sur la liste, les stats affichent un bonus (« 4088 ▲2708 ») : on ne les lit **que** sur la fiche.

## Pipeline de lecture (`scanner/hero_scanner.py`)
1. **Panneau de stats** : 9 lignes à ordre fixe (ATK, DEF, PV, VIT, CC, DC, EFF, RES, AD).
   Valeurs lues ligne par ligne (reconnaissance sans détection, sans correction de rotation).
2. **Icônes de stats apprises sur la capture elle-même** : les icônes du panneau (libellé connu)
   servent de modèles pour classer les icônes des stats d'équipement (`vision/icons.py::features`,
   seuillage d'Otsu + recadrage sur le glyphe). ATK/DEF/PV + « % » → variante pourcentage.
3. **Stat principale contrainte** par emplacement (arme = ATK, casque = PV, armure = DEF, etc.).
4. **Sets** (`vision/set_catalog.py`) : une capture du catalogue des sets (filtre d'inventaire)
   donne les 24 blasons ; chacun est recadré sur fond noir et enregistré dans
   `<dossier de données>/templates/sets/<set>.png`. Sur la fiche, le blason de chaque pièce est
   retrouvé par corrélation multi-échelle (glissement + tailles 0,8 → 1,25) sur l'intérieur du
   blason. Seuil 0,78 : bon set ≥ 0,91, meilleur mauvais set ≤ 0,63 sur captures réelles ;
   paire de blasons la plus proche : Protection / Implication (0,70). Set inconnu → `None`.
   Sans catalogue, la **liste des héros** suffit pour les sets portés : chaque ligne « Set Xxx »
   montre le blason à côté de son nom (`HeroScanner.learn_list_sets`) ; un blason du catalogue
   reste prioritaire. Sur PC : bon set ≥ 0,93, meilleur mauvais set ≤ 0,52.
5. **Icônes perturbées par le décor** (ex. cristaux de glace de Coli tactique) : une seconde
   lecture ignore les formes qui touchent le bord de la boîte (`features(drop_border=True)`),
   le meilleur score des deux est retenu.
6. **Captures plein écran Windows** (« Impr. écran » de la fenêtre agrandie) : la barre de titre
   et la barre des tâches sont retirées automatiquement (`vision/preprocess.strip_window_chrome`)
   avant le choix du profil et la lecture ; `.png`, `.jpg` et `.webp` sont acceptés.

Aucune image du jeu n'est livrée : les modèles viennent des captures de l'utilisateur.

## Précision mesurée
**Client PC** (fenêtre agrandie sur écran 1920×1080, zone cliente 1919×1009, client FR), 2 héros
réels avec les captures brutes (barre de titre et barre des tâches comprises) :
**138/138 valeurs exactes (100 %)**, 12/12 sets appris depuis 2 listes des héros, sans catalogue.

**Mobile** : sur 3 héros réels (captures mobiles 3120×1440, client FR) : **206/207 valeurs exactes (99,5 %)**,
18/18 sets (appris uniquement depuis le catalogue), ~3 s par héros sur CPU. Mesure reproductible :
```bash
python scripts/evaluate_captures.py <dossier local>         # voir le format dans le script
E7_TEST_CAPTURES=<dossier local> pytest tests/test_real_captures.py
```

## Profils de zones (`config/regions/`)
| Profil | Format | État |
|---|---|---|
| `19_5x9.toml` | 2,167 (smartphones récents) | **calibré** sur captures réelles |
| `pc_19x10.toml` | 1,902 (PC, fenêtre agrandie en 1920×1080) | **calibré** sur captures réelles (100 %) |
| `16x9.toml` | 1,778 (PC plein écran 1920×1080, 2560×1440) | **estimé** depuis `pc_19x10` (`scripts/derive_profile.py`), à vérifier |

`region_profile = "auto"` choisit le profil au format le plus proche de la fenêtre ou des captures.
Pour un nouveau format PC : `python scripts/derive_profile.py config/regions/pc_19x10.toml <largeur/hauteur>`
puis calibrer (skill `calibrate-ocr-regions`).

## Ajouter une langue
1. Libellés dans `data/reference/stat_aliases.json` et `classes.json` (clés normalisées).
2. Noms de sets (`sets.json`) et de héros (`heroes.json`).
3. Indices de reconnaissance d'écran (`is_detail_screen`, `is_list_screen`).
4. Vérité terrain de quelques héros + `scripts/evaluate_captures.py`.

## Erreurs OCR connues et parades
| Symptôme | Parade |
|---|---|
| « 9% » lu « %6 » (texte retourné) | `parsers/common.clean` + reconnaissance sans rotation |
| « 7% » lu « 17% » (bord d'icône) | marge `values_dx` calibrée |
| niveau « 90 » illisible | valeur hors bornes → `None` |
| icône de stat ambiguë (1/81 mesuré) | à améliorer : plusieurs modèles par stat |
| décor clair qui déborde sur une icône (VIT lue DEF) | seconde lecture sans les formes touchant le bord |
| titre lu « Infos de eros » | reconnaissance tolérante (« infos » + « ero ») |
