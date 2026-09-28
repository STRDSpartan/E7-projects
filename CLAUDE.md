# E7 Showcase — guide pour Claude

Scanner de roster du **client PC Epic Seven** (capture d'écran + OCR, ou import Fribbels) qui
génère des **vitrines PNG** partageables sur **Discord** au sein d'une guilde.
Langue du projet : documentation et messages utilisateur en **français**, code et identifiants en anglais.

## Commandes
```bash
pip install -e ".[dev]"          # + [scan] [render] [bot]
ruff format . && ruff check . && mypy && pytest     # définition de « terminé » (skill dev-checks)
e7showcase --help
```

## Carte du code (`src/e7showcase/`)
`models/` Pydantic (Roster = format d'échange, `SCHEMA_VERSION`) · `reference.py` + `data/reference/`
· `calc/` gear score & sets · `parsers/` texte OCR → modèles (purs, très testés) · `capture/` fenêtre
+ capture (Windows) · `vision/` ROI normalisées, prétraitement, OCR · `scanner/` orchestration ·
`importers/fribbels.py` · `storage/` JSON · `assets.py` portraits locaux · `sources/e7codex.py` référentiel & sync · `render/` Jinja2 → PNG Playwright · `publish/` webhook & bot
· `cli.py` Typer. Détails : `docs/ARCHITECTURE.md`.

## Règles non négociables
1. **Conformité** (`docs/COMPLIANCE.md`) : jamais de lecture mémoire, d'interception réseau,
   d'injection ou de modification du client. Clics automatisés seulement dans `AssistedNavigator`
   (désactivé par défaut).
2. **Aucun secret, capture, roster réel ou asset du jeu** dans le dépôt.
3. Capturer ≠ comprendre ; parseurs sans I/O ; ROI toujours normalisées.
4. Imports lourds (`mss`, `cv2`, `rapidocr_onnxruntime`, `win32*`, `keyboard`, `playwright`,
   `discord`) **dans les fonctions**, pour que le cœur s'importe sans extras.
5. Rupture du format `Roster` → incrémenter `SCHEMA_VERSION` + migration.
6. mypy strict, ruff, tests verts avant tout commit ; ne jamais désactiver un test.

## Agents (`.claude/agents/`) et skills (`.claude/skills/`)
Voir `docs/AGENTS.md`. En bref : `e7-architect` planifie, puis `vision-ocr-engineer`,
`e7-game-data-specialist`, `showcase-designer`, `discord-integrator` implémentent,
`qa-engineer` teste, `compliance-reviewer` valide. Skills : `e7-domain`,
`calibrate-ocr-regions`, `e7-reference-data`, `render-showcase`, `discord-integration`, `dev-checks`.

## Environnement
- Le scan réel nécessite Windows + le client lancé ; ailleurs, travailler sur des captures
  enregistrées (`tests/fixtures/captures/`).
- Rendu PNG : `E7_CHROMIUM_PATH` peut pointer vers un Chromium existant
  (conteneur web : `/opt/pw-browsers/chromium-*/chrome-linux/chrome`, exporté par le hook SessionStart).
- Carte animée (`render --animated`) : Chromium doit faire confiance au proxy du conteneur,
  voir la skill `render-showcase` (ne jamais désactiver la vérification TLS).
- Utiliser `E7_DATA_DIR=$(mktemp -d)` pour ne pas écraser le roster de l'utilisateur pendant les essais.
- Mesure de précision du scan : `scripts/evaluate_captures.py` sur un dossier LOCAL de captures + `expected.json` (jamais committé).
