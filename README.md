# E7 Showcase

Scanner de roster pour le **client PC d'Epic Seven** (Stove / bientôt Steam) qui génère des
**vitrines visuelles partageables sur Discord** — pour que la guilde puisse se concerter, drafter
ses équipes GvG / RTA / Boss et comparer les builds.

```
 Client PC E7 ──capture écran──► OCR ──► Roster JSON ──► Vitrine PNG ──► Discord (webhook / bot)
 Export Fribbels ─────────────────────────┘                    ▲
                                             tags guilde, filtres, draft
```

## Fonctionnalités

| Module | Rôle | État |
|---|---|---|
| `capture/` | Localise la fenêtre du jeu, capture la zone cliente (Windows) | fonctionnel, à tester sur client réel |
| `vision/` | Découpage des zones (ROI normalisées), pré-traitement, OCR (RapidOCR / Tesseract) | fonctionnel, **ROI à calibrer** |
| `parsers/` | Texte OCR → stats, équipements, sets, nom du héros (FR/EN, tolérant au bruit) | testé |
| `scanner/` | Boucle de scan héros par héros, mode manuel (touche F9) ou assisté | fonctionnel |
| `importers/` | Import d'un export **Fribbels E7 Optimizer** (alternative sans OCR) | testé sur échantillon |
| `calc/` | Gear score (formule communautaire), sets actifs | testé |
| `storage/` | Roster local JSON (= format d'échange guilde) | testé |
| `render/` | Vitrine HTML (Jinja2) → PNG (Playwright), mise en page cartes ou grille | testé |
| `publish/` | Publication Discord par webhook, bot `/vitrine` `/draft` `/roster-upload` | squelette bot |

## Installation

```bash
python -m venv .venv && .venv\Scripts\activate        # Windows (source .venv/bin/activate ailleurs)
pip install -e ".[scan,render,dev]"                     # + ".[bot]" pour le bot Discord
playwright install chromium
copy .env.example .env                                  # puis renseigner E7_DISCORD_WEBHOOK_URL
```

## Utilisation

```bash
e7showcase scan --player "MonPseudo"          # F9 = capturer, F8 = passer un emplacement, F10 = terminer
e7showcase import-fribbels export.json        # alternative : import depuis Fribbels
e7showcase list                               # tableau du roster
e7showcase tag "Ras" GvG-def                  # tags pour la guilde
e7showcase render --layout grid               # vitrine complète en grille → out/*.png
e7showcase render "Ras" "Sigret"              # cartes détaillées de héros choisis
e7showcase share "Ras" --message "Mon Ras GvG"  # publication sur le salon Discord
e7showcase export                             # roster JSON à partager / déposer au bot
```

### Déroulé d'un scan manuel
1. Lancer le jeu en **16:9 fenêtré** (1920×1080 conseillé), ouvrir *Héros* → fiche détails du premier héros.
2. `e7showcase scan` → **F9** sur la fiche, puis pour chaque emplacement (arme → bottes) :
   cliquer la pièce en jeu pour ouvrir l'infobulle et **F9** (ou **F8** si vide).
3. Passer au héros suivant en jeu, recommencer. **F10** pour terminer.

Les captures sont conservées dans le dossier de données (`save_captures`) pour recalibrer l'OCR.

## Documentation
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — flux de données, modules, décisions
- [docs/SCANNING.md](docs/SCANNING.md) — calibration des zones OCR, ajout de résolutions / langues
- [docs/COMPLIANCE.md](docs/COMPLIANCE.md) — conformité aux CGU de Smilegate, vie privée
- [docs/ROADMAP.md](docs/ROADMAP.md) — jalons du projet
- [docs/AGENTS.md](docs/AGENTS.md) — agents et skills Claude Code du projet

## Développement
```bash
pytest            # tests
ruff check .      # lint
mypy              # typage
```

> Projet communautaire non affilié à Smilegate. Epic Seven est une marque de Smilegate Megaport.
