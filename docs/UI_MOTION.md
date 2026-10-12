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
| Dialogues | ouverture à ressort, fond flouté |

## Accessibilité et performance
- `prefers-reduced-motion: reduce` : animations, transitions et particules coupées.
- Bouton « ✨ Effets visuels » (bas de la barre latérale) : coupe tout (`html.no-fx`), choix
  mémorisé dans le navigateur (`localStorage` `e7-fx`, facultatif).
- Seuls `transform`, `opacity` et `filter` sont animés ; la boucle de particules ne tourne
  que si les effets sont actifs et la fenêtre visible.
