---
name: render-showcase
description: Générer, prévisualiser et itérer sur les vitrines PNG (cartes héros, grille de roster) destinées à Discord - données d'exemple, rendu Playwright, vérification visuelle de l'image. À utiliser pour toute modification de src/e7showcase/render ou pour produire une vitrine.
---

# Générer et vérifier une vitrine

## Préparer des données
```bash
export E7_DATA_DIR="$(mktemp -d)"          # ne pas toucher au roster réel de l'utilisateur
e7showcase import-fribbels tests/fixtures/fribbels_export.json --player Démo
e7showcase tag Ras GvG-def
```
Pour tester les cas limites, créer un roster plus riche (6 pièces, noms longs, 9 stats,
héros sans équipement) via un petit script Python utilisant `models.Roster`.

## Portraits (facultatif)
Images locales uniquement (`<E7_DATA_DIR>/assets/heroes|artifacts/<clé>.webp`, clé = code `c1001`
ou nom slugifié FR/EN) : `e7showcase assets add hero "Kise" img.png`, `e7showcase assets status`.
Pour tester la mise en page, générer des **portraits synthétiques** (Pillow) — jamais de visuels
du jeu dans le dépôt ni dans les tests. Vérifier les deux cas : carte avec et sans portrait.

## Rendre
```bash
e7showcase render --out out/                # cartes détaillées (≤ 6 par image)
e7showcase render --layout grid --out out/  # grille compacte
e7showcase render --html-only --out out/    # HTML seul (sans navigateur)
```
Navigateur : `playwright install chromium`, ou pointer `E7_CHROMIUM_PATH` vers un
Chrome/Edge/Chromium existant (dans un conteneur Claude Code :
`/opt/pw-browsers/chromium-*/chrome-linux/chrome`).

## Vérifier visuellement (obligatoire)
Ouvrir chaque PNG produit avec l'outil Read et contrôler :
- aucun débordement ni texte coupé, marges symétriques, pas de grand vide en bas ;
- lisibilité à 50 % (aperçu mobile Discord) ;
- pièces vides grisées, sets et gear score cohérents avec `e7showcase list`.

## Contraintes
Pas de ressources distantes dans les templates ; pas d'assets du jeu committés ;
autoescape Jinja2 conservé (les noms/tags viennent de l'utilisateur).
Finir par la skill `dev-checks`.
