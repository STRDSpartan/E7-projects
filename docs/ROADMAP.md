# Roadmap

## M0 — Fondations ✅ (ce commit)
- Modèles, parseurs FR/EN, gear score, sets, import Fribbels, stockage JSON
- Rendu HTML/PNG (cartes + grille), webhook Discord, CLI, squelette bot
- Configuration agents & skills Claude Code, CI

## M1 — Scan fiable sur client réel
- [x] Lecture complète depuis « Infos de héros » (une capture par héros)
- [x] Profil 19,5:9 calibré sur captures réelles — 99,5 % sur 207 valeurs
- [x] Icônes de stats apprises sur la capture
- [x] 24 blasons de sets appris depuis une capture du catalogue (18/18 sur pièces réelles)
- [x] Choix automatique du profil selon le format ; `scan --from-dir` (mobile / hors-ligne)
- [ ] Calibrer `16x9.toml` sur de vraies captures PC 1920×1080
- [ ] Étoiles, éveil, rang d'empreinte (SSS…), équipement exclusif
- [ ] Noms anglais de « Affaiblissement », « Réaction », « Engagement », « Implication »
      (correspondance avec Warfare / Reversal côté Fribbels) et nombre de pièces à confirmer
- [ ] Contrôle de cohérence : stats de la fiche ≈ base du héros + équipement

## M2 — Vitrine
- [x] Portraits des héros et images d'artefacts depuis le dossier local (`e7showcase assets`)
- [x] Référentiel complet depuis e7codex.com (390 héros, 66 skins, 282 artefacts, noms FR/EN)
- [x] `e7showcase assets sync` : poses, visages, skins, artefacts des héros du roster (local)
- [x] Correction des noms d'artefacts lus par l'OCR d'après le référentiel
- [ ] Thèmes (par élément, par guilde), logo de guilde
- [ ] Moteur Pillow de secours sans navigateur
- [ ] Vue « équipe » (4 héros GvG/RTA côte à côte)

## M3 — Guilde
- [ ] Bot : `/roster-delete`, `/equipe`, `/qui-a <héros> --vitesse>=200`
- [ ] Tableau de draft GvG (défenses par tour, attribution des attaques)
- [ ] Export CSV / Google Sheets

## M4 — Distribution
- [ ] Exécutable Windows (PyInstaller) + installateur
- [ ] Interface graphique légère (overlay de guidage du scan)
- [ ] Suivi des changements de l'UI après chaque mise à jour du client (Steam)
