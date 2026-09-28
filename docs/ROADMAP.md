# Roadmap

## M0 — Fondations ✅ (ce commit)
- Modèles, parseurs FR/EN, gear score, sets, import Fribbels, stockage JSON
- Rendu HTML/PNG (cartes + grille), webhook Discord, CLI, squelette bot
- Configuration agents & skills Claude Code, CI

## M1 — Scan fiable sur client réel
- [x] Lecture complète depuis « Infos de héros » (une capture par héros)
- [x] Profil 19,5:9 calibré sur captures réelles — 99,5 % sur 207 valeurs
- [x] Icônes de stats apprises sur la capture ; icônes de sets apprises (liste + fiche)
- [x] Choix automatique du profil selon le format ; `scan --from-dir` (mobile / hors-ligne)
- [ ] Calibrer `16x9.toml` sur de vraies captures PC 1920×1080
- [ ] Étoiles, éveil, rang d'empreinte (SSS…), équipement exclusif
- [ ] Nom anglais du set « Affaiblissement »
- [ ] Contrôle de cohérence : stats de la fiche ≈ base du héros + équipement

## M2 — Vitrine
- [ ] Portraits des héros (assets fournis par l'utilisateur, jamais redistribués dans le dépôt)
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
