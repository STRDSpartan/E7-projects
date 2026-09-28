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
Images locales uniquement (`<E7_DATA_DIR>/assets/heroes|faces|artifacts/<clé>.webp`, clé = code
`c1006` / `art0243` ou nom slugifié FR/EN) : `e7showcase assets sync` (e7codex, héros du roster),
`e7showcase assets add hero "Kise" img.png`, `e7showcase assets status`.
Pour tester la mise en page, générer des **portraits synthétiques** (Pillow) — jamais de visuels
du jeu dans le dépôt ni dans les tests. Vérifier les deux cas : carte avec et sans portrait.

## Carte animée
`e7showcase render "Kise" --animated` : exporte (une fois, cache `assets/anims/<code>.webp`) le
modèle via la visionneuse d'E7 Codex (`sources/e7codex.export_animation`), puis
`render/animated.py` incruste chaque image dans la zone `.anim-slot` de la carte → WebP animé
(réduit sous 9,5 Mo). Vérifier plusieurs images de l'animation (début, milieu), pas seulement
la première : un cadrage faussé par des particules rapetisse le personnage.

Dans un conteneur Claude Code, Chromium doit passer par le proxy (géré par `export_animation`
via `HTTPS_PROXY`) et faire confiance à son autorité : si `ERR_CERT_AUTHORITY_INVALID`,
`certutil -A -d sql:$HOME/.pki/nssdb -t "C,," -n ccr-agent-proxy -i /root/.ccr/agent-proxy-ca.crt`
(paquet `libnss3-tools`). Ne jamais désactiver la vérification TLS.

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
