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
| Dialogues | ouverture à ressort, fond flouté |

## Accessibilité et performance
- `prefers-reduced-motion: reduce` : animations, transitions et particules coupées.
- Bouton « ✨ Effets visuels » (bas de la barre latérale) : coupe tout (`html.no-fx`), choix
  mémorisé dans le navigateur (`localStorage` `e7-fx`, facultatif).
- Seuls `transform`, `opacity` et `filter` sont animés ; la boucle de particules ne tourne
  que si les effets sont actifs et la fenêtre visible.
