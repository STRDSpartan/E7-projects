---
name: ui-motion
description: Faire évoluer et vérifier l'esthétique et les animations de l'application de bureau (ui.html) - thème doré, transitions d'onglets, apparitions en cascade, particules, ondulations, compteurs - avec captures Chromium et contrôle des erreurs JS. À utiliser pour tout changement visuel de l'application.
---

# Animer et vérifier l'interface de l'application

Référence : `docs/UI_MOTION.md` (inventaire des effets et règles).

## Où intervenir
- CSS : bloc « Esthétique et animations » à la fin du `<style>` de `src/e7showcase/app/ui.html`.
- JS : module `fx` à la fin du `<script>` (`fx.transition`, `fx.burst(x, y, n)`, `fx.burstAt(node)`).
- Les nouvelles pages n'ont rien à faire : cartes (`.card`), tuiles (`.tile`), pièces (`.gear`)
  et lignes de tableau apparaissent en cascade automatiquement ; une `.wins` déclenche une gerbe.

## Vérifier dans Chromium (sans fenêtre native)
```python
from e7showcase.app.server import AppState, start_server  # E7_DATA_DIR temporaire !

srv = start_server(AppState(tmp_dir))
# playwright : executable_path = /opt/pw-browsers/chromium-*/chrome-linux/chrome
page.on("pageerror", ...)  # aucune erreur JS tolérée
page.click('.topnav [data-tab="guild"]')
page.wait_for_timeout(250)  # capture mi-transition
page.wait_for_timeout(1200)  # capture finale
page.click("#fx-toggle")  # effets coupés : tout doit rester utilisable
```
Regarder les captures : texte lisible (onglet actif, boutons dorés), pas de contenu masqué,
indicateur sous l'onglet actif. Tester aussi `reduced_motion="reduce"` dans `new_page`.

## Puis
`ruff format . && ruff check . && mypy && pytest` (skill `dev-checks`).
