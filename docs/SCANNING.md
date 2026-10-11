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
   **Blasons de référence** (`sources/set_icons.py`) : au premier import de fiches, l'application
   télécharge les icônes publiques des 24 sets (base Hideout Guides) dans cette même bibliothèque
   locale, recadrées comme un blason lu en jeu, sans jamais remplacer un blason appris. Avec ces
   seules icônes : 18/18 pièces de 720p à 4K, bon set ≥ 0,93, meilleur mauvais set ≤ 0,66.
   Aucune capture préalable de la liste ou du catalogue n'est donc nécessaire.
5. **Icônes perturbées par le décor** (ex. cristaux de glace de Coli tactique) : une seconde
   lecture ignore les formes qui touchent le bord de la boîte (`features(drop_border=True)`),
   le meilleur score des deux est retenu.
6. **Captures plein écran Windows** (« Impr. écran » de la fenêtre agrandie) : la barre de titre
   et la barre des tâches sont retirées automatiquement (`vision/preprocess.strip_window_chrome`)
   avant le choix du profil et la lecture ; `.png`, `.jpg` et `.webp` sont acceptés.

Aucune image du jeu n'est livrée : les modèles viennent des captures de l'utilisateur.

## Précision mesurée
**Client PC** (fenêtre agrandie sur écran 1920×1080, zone cliente 1919×1009, client FR), 3 héros
réels (Kise, Coli tactique, Ludwig Prélude de l'Aubade) avec les captures brutes (barre de titre et
barre des tâches comprises) : **207/207 valeurs exactes (100 %)**, 18/18 sets appris depuis
2 listes des héros, sans catalogue.

**Mobile** : sur 3 héros réels (captures mobiles 3120×1440, client FR) : **206/207 valeurs exactes (99,5 %)**,
18/18 sets (appris uniquement depuis le catalogue), ~3 s par héros sur CPU. Mesure reproductible :
```bash
python scripts/evaluate_captures.py <dossier local>         # voir le format dans le script
E7_TEST_CAPTURES=<dossier local> pytest tests/test_real_captures.py
```

## Toutes les résolutions et tous les formats (`vision/layouts.py`)
- **Résolution** : chaque capture est remise à la hauteur des captures de calibration du profil
  (`reference_height` : 1009 px PC, 1440 px mobile). Mesuré sur les 3 héros réels, captures
  redimensionnées : **720p, 768p, 900p, 1080p, 1440p, 4K → 204/204 (100 %)**. Sans cette étape,
  la 1440p tombait à ~50 %.
- **Format** (16:9, 16:10, 21:9, 32:9, 4:3, fenêtre agrandie, mobile 20:9…) : les profils
  marqués `calibrated = true` sont transposés au format EXACT de la capture (panneaux ancrés à
  gauche / à droite / au centre, distances conservées en unités de hauteur). Les formats non
  encore vus sur de vraies captures sont donc estimés : à vérifier avec une capture.
- **Ambiguïté PC / mobile** : si une fiche se lit mal (moins de 6 pièces), l'autre profil
  calibré est essayé et la lecture la plus complète est gardée.
- **Barres Windows** : retirées même sur une capture rééchantillonnée (liseré toléré).
- **Cadrage de la capture** : tous les cadrages donnent 204/204 sur les captures réelles —
  jeu seul, fenêtre avec barre de titre (Alt+Impr. écran), jeu + barre des tâches, écran
  complet, **barre de titre en thème sombre**, **sélection Win+Maj+S avec marges**. Les deux
  derniers cas sont recadrés par repères (`vision/framing.py`, `[detail.landmarks]`) : le
  titre « Infos de héros » et « Chances de double attaque » donnent l'échelle et le haut/la
  gauche du jeu, « Score moyen d'équipements » (ancré à droite) le bord droit.
- **Nom du héros** : la zone est coupée avant les étoiles (sinon « Kise ★★★ » était lu
  « Kise Aan », un autre héros).

## Profils de zones (`config/regions/`)
| Profil | Format | État |
|---|---|---|
| `19_5x9.toml` | 2,167 (smartphones récents) | **calibré** sur captures réelles |
| `mobile_20x9.toml` | 2,222 (smartphones 20:9, captures 2000×900) | **calibré** sur 5 fiches réelles : 100 % (puissance, 9 stats, 30 pièces : set, score, principale, 120 secondaires) |
| `pc_19x10.toml` | 1,902 (PC, fenêtre agrandie en 1920×1080) | **calibré** sur captures réelles (100 %) |
| `16x9.toml` | 1,778 (PC plein écran 1920×1080, 2560×1440) | **estimé** depuis `pc_19x10` (`scripts/derive_profile.py`), à vérifier |

`region_profile = "auto"` choisit le profil au format le plus proche de la fenêtre ou des captures.
Une capture au format exact d'un profil calibré (à 1 % près) n'est jamais recadrée par les
repères PC (`NATIVE_ASPECT`). Les petites icônes de stats sont agrandies ×3 avant seuillage
(`vision/icons.py`) : sans cela, le bouclier (Défense) des colliers mobiles était lu comme
un cœur (Santé).

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
