# Esthétique et animations de l'application

Tout est dans `src/e7showcase/app/ui.html` (CSS en fin de `<style>`, module JS `fx` en fin de
`<script>`), sans ressource externe. Agent : `ui-motion-designer` ; skill : `ui-motion`.

| Effet | Détail |
|---|---|
| Thème | fond à halos bleu/or, panneaux vitrés (flou), boutons dorés en dégradé, titres de carte à puce lumineuse, barres de défilement fines |
| Logo | reflet doré qui balaie « E7 SHOWCASE » |
| Onglets | indicateur doré qui glisse sous l'onglet actif ; transition sortie (150 ms) puis entrée glissée dans le sens de navigation (droite/gauche) |
| Apparitions | cartes, tuiles, pièces d'armurerie, lignes des membres et profils de la liste apparaissent en cascade |
| Micro-interactions | ondulation au clic, étincelles sur les boutons principaux, survol qui soulève les cartes avec halo suivant la souris, icône de pièce qui pivote, focus doré |
| Compteurs | les chiffres des tuiles montent depuis 0 |
| Résultats | barre victoires/défaites qui se remplit, gerbe d'étincelles à chaque résultat de simulation et à la fin d'un import de guilde |
| Particules | poussière dorée et bleue qui monte lentement en fond (canvas, ≤ 70 particules, arrêtée fenêtre cachée) |
| Icônes | pictogramme SVG par onglet (s'anime au survol, halo sur l'onglet actif) ; icône de fenêtre (hexagone « E7 ») |
| Accueil | emblème « E7 » animé (anneaux qui tournent, cœur qui respire), étapes numérotées en cartes |
| Notifications | toasts en bas à droite (succès ✓ vert, avertissement or, erreur ! rouge), fermeture au clic ou automatique ; remplacent les `alert()` (les `confirm()` restent) |
| Armurerie | cartes teintées par rang (épique rouge, héroïque violet, rare bleu) ; badge « De côté » sur les pièces non équipées |
| Chargement | silhouette scintillante si une page met plus de 180 ms à arriver |
| Portraits de héros | `portrait(nom)` : visage (assets locaux, sinon portrait découpé d'une capture, sinon initiales) dans un cadre à la couleur de l'élément (feu, glace, terre, lumière, ténèbres), étoiles en bas, élément/classe en info-bulle, reflet au survol. Infos chargées par lots : `POST /api/portraits` (`app/portraits.py`) |
| GvG | défenses : avatar du membre, tour avec icône, aperçu des équipes en portraits (emplacements vides en pointillés) au-dessus des sélecteurs ; attaques : portraits des deux équipes, badge « VS », résultat en pastille, liseré vert/rouge ; attaques restantes en jauges ; contres : portraits de la défense, barre victoires/défaites, lignes colorées selon le bilan |
| Guilde, armurerie | héros phares en portraits ; mini-portrait du porteur sur chaque pièce |
| Rejeu de combat | bouton « ▶ Revoir le combat type » sous chaque simulation : arène attaque/défense avec portraits, barres de PV (traînée dorée des dégâts, barre rouge pulsante sous 30 %, bouclier hachuré), héros actif mis en avant, chiffres de dégâts (rouge) et de soins (vert) qui s'envolent, secousse à l'impact, K.O. en gris avec étincelles, journal du tour, bannière du vainqueur ; pause, vitesse ×1/×2/×4, aller à la fin. Données : `sample.frames` / `sample.units` de `calc.battle.simulate` (PV après chaque tour) |
| Simulateur | équipes A (bleu) et B (rouge) face à face autour d'un « VS », 4 places en portraits mises à jour à chaque choix ; rejeu animé aussi dans le simulateur principal |
| Profils (barre latérale) | pastille ronde à l'initiale, couleur propre à chaque joueur (liseré bleu pour une vitrine reçue, halo doré pour le profil ouvert) |
| Formulaires | cases à cocher dorées, rebond au clic |
| Verdict | à la fin de chaque simulation (simulateur, tests GvG) : bandeau « Victoire » aux couleurs de l'équipe gagnante (A bleu, B rouge), trophée qui surgit, rayons qui tournent, reflet qui balaie, taux de victoire qui monte jusqu'à sa valeur, gerbe d'étincelles ; « Combat serré » ⚖ en or si l'écart est sous 10 points ; amené à l'écran automatiquement |
| Relevés GvG | équipe adverse encadrée de rouge, badges « reconnu » (vert) / « à vérifier » (or, pulsant), propositions en pastilles, portraits découpés sur la capture |
| Carte de la guerre | panorama (image de fond du joueur ou panorama dessiné) au ratio exact de l'image pour que les boutons restent sur les châteaux ; nos forteresses à gauche (anneau vert, 🛡), adverses à droite (anneau rouge, ⚔), plaque avec le nom court ; « VS » et temps restant au centre ; barre de Ravage. Boutons centrés avec `translate` (les effets de survol des boutons modifient `transform`) : ils ne bougent plus au survol ; pas d'ondulation sur ces boutons |
| Coller (Ctrl+V) | mention dorée « ou collez-la avec Ctrl+V » dans chaque zone d'import ; onde dorée sur la zone qui reçoit la capture, notification « Capture collée » |
| Dialogues | ouverture à ressort, fond flouté |

## Accessibilité et performance
- `prefers-reduced-motion: reduce` : animations, transitions et particules coupées.
- Bouton « ✨ Effets visuels » (bas de la barre latérale) : coupe tout (`html.no-fx`), choix
  mémorisé dans le navigateur (`localStorage` `e7-fx`, facultatif).
- Seuls `transform`, `opacity` et `filter` sont animés ; la boucle de particules ne tourne
  que si les effets sont actifs et la fenêtre visible.

## Identité « nuit de sakura » (v0.56)

Inspirée de la vidéo de fond du bandeau des profils (`app/media/sidebar.webm`, fournie par
l'éditeur, réencodée en VP9 360×640 sans son, ~0,9 Mo) : fond bleu nuit `--bg #060818`, accent
principal lavande lumineuse `--gold #b9a0ff` (le nom de variable est historique), bleu `--accent
#7fb4ff`, rose `--sakura #ff9fd4`, lanterne `--lantern #f4c980`. Les particules deviennent des
pétales roses et des lueurs bleues. La vidéo est masquée avec « Effets visuels : désactivés » et
`prefers-reduced-motion`. Icône et installateur (`scripts/make_icon.py`) suivent la même palette.

## Logo (v0.57)

Logo officiel fourni par l'éditeur : `packaging/branding/zealot-logo.png`. `scripts/make_icon.py`
en tire l'icône (emblème sur pastille violette), les images de l'installateur et, avec `--app`,
`app/media/logo.png` (écran d'accueil) et `app/media/emblem.png` (bandeau, favicon), fond rendu transparent.
