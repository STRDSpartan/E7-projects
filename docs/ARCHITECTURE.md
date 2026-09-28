# Architecture

## Flux de données

```
┌──────────── Acquisition ────────────┐   ┌─ Domaine ─┐   ┌────── Restitution ──────┐
 capture/window  → capture/screenshot
        │ PIL.Image
 vision/regions (ROI normalisées) → vision/ocr → parsers/*  ──►  models.Roster  ──► render/viewmodel
                                                    ▲              │   ▲              │
 importers/fribbels (JSON) ─────────────────────────┘              ▼   │        render/showcase
                                                          storage/repository   (HTML → PNG)
                                                          (roster.json)              │
                                                                               publish/webhook
                                                                               publish/bot
```

## Principes

1. **Capturer ≠ comprendre.** `scanner/session.py` ne fait que prendre des captures ;
   `scanner/hero_scanner.py` ne fait que les interpréter. Tout le pipeline d'extraction est
   testable hors-jeu à partir de PNG enregistrés (`tests/fixtures/captures/`).
2. **Parseurs purs.** `parsers/` transforme du texte en modèles, sans I/O : c'est la zone la plus
   testée, et le premier endroit où corriger une erreur OCR.
3. **Coordonnées normalisées.** Les ROI de `config/regions/*.toml` sont en fractions de la zone
   cliente, donc indépendantes de la résolution pour un même ratio (un fichier par ratio).
4. **Un seul format d'échange.** `models.Roster` sérialisé en JSON sert au stockage local, à
   l'export vers la guilde et à l'upload au bot. Tout changement incompatible incrémente
   `SCHEMA_VERSION`.
5. **Lecture seule vis-à-vis du jeu.** Aucune lecture mémoire, aucune interception réseau,
   aucune modification de fichiers du client (voir `COMPLIANCE.md`).
6. **Dépendances lourdes optionnelles.** OCR (`[scan]`), navigateur (`[render]`) et discord.py
   (`[bot]`) sont des extras ; le cœur (modèles, parseurs, rendu HTML) reste léger.

## Modules

| Chemin | Responsabilité | Dépend de |
|---|---|---|
| `models/` | Pydantic : `StatType`, `Gear`, `Hero`, `Roster` | — |
| `reference.py` + `data/reference/` | Sets, alias de stats FR/EN, référentiel héros | — |
| `calc/` | Gear score, sets actifs | models, reference |
| `parsers/` | Texte OCR → StatLine / Gear / HeroStats, fuzzy-matching des noms | models, reference |
| `capture/` | Fenêtre du jeu (win32), capture (mss) | — |
| `vision/` | ROI, pré-traitement, moteurs OCR | PIL |
| `scanner/` | Orchestration du scan, navigateurs (manuel/assisté) | capture, vision, parsers |
| `importers/` | Fribbels E7 Optimizer | models |
| `storage/` | Persistance JSON atomique | models, config |
| `render/` | ViewModel, templates Jinja2, rendu PNG Playwright | models, calc |
| `publish/` | Webhook Discord, bot slash-commands | render, storage |
| `cli.py` | Commandes Typer | tout |

## Décisions (ADR courts)

- **OCR plutôt qu'interception réseau / lecture mémoire** : conformité CGU et robustesse aux
  mises à jour du client ; coût : calibration des ROI par ratio d'écran.
- **RapidOCR par défaut** : pas d'installation système (contrairement à Tesseract), bon sur
  chiffres et latin accentué, tourne sur CPU.
- **HTML + Playwright pour le rendu** : itération visuelle rapide (CSS), rendu fidèle des polices ;
  Pillow reste possible comme moteur de secours sans navigateur (`render.engine = "pillow"`, à implémenter).
- **Webhook avant bot** : zéro hébergement pour le cas principal (« je partage ma vitrine ») ;
  le bot sert les cas collectifs (draft, recherche de héros dans la guilde).
