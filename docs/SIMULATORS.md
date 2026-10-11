# Simulateurs de dégâts et de combat

Bouton **⚔ Simulateurs** de l'application. Les héros des profils (et des vitrines reçues)
servent de combattants avec leurs stats finales lues sur les captures.

## Données
`data/reference/skills.json` : multiplicateurs de chaque compétence (taux, puissance,
amélioration par molagora, pénétration, bonus fixes sur PV / défense / vitesse, zone ou cible
unique, version âme brûlée) pour 400 héros. Générés par `scripts/update_skills.py` à partir du
calculateur communautaire **E7Calc** (https://e7calc.xyz,
https://github.com/tyopoyt/epic7-damage-calc, licence ISC) : ses fonctions de compétences sont
exécutées dans Node avec des conditions neutres. Aucun code tiers n'est embarqué. Les bonus
conditionnels propres à un héros (cible avec un buff, PV restants...) sont signalés
(`conditional`, « † » dans l'interface) mais non appliqués.

## Formule (`calc/damage.py`)
```
attaque  = attaque finale × (1 + buffs d'attaque : +50 %, +75 %, −50 %)
offensif = ((attaque × taux + bonus fixe) × 1,871) × puissance × (1 + amélioration)
           × 1,1 si avantage élémentaire × (1 + bonus de dégâts, Rage +30 %, Tumulte +10 %)
défensif = (1 − réduction) / ((défense cible × (1 + mod. défense) / 300) × (1 − pénétration) + 1)
critique = normal × min(dégâts critiques, 350 %) ; écrasant ×1,3 ; raté ×0,75
```
Vérifié à la main (Kise S3, 4 088 ATQ, 290 % DC, cible 1 000 DÉF : 3 671 / 10 647).

## Effets des compétences
`skills.json` contient aussi, par compétence, `cooldown` (recharge réelle après améliorations),
`passive` et `effects`, tirés des pages héros de la base publique **E7GW** (https://e7gw.xyz,
`/hero` autorisé par son robots.txt) et analysés par `parsers/skill_effects.py` : les
étiquettes d'effets (« Heal », « Increase Attack », « Stun »...) disent quels effets existent,
le texte donne la cible, la durée et la probabilité. 384 héros, 868 compétences avec effets.
Les barrières reprennent les coefficients d'E7Calc (70 héros, ex. Kise : 65 % de l'attaque) ;
les soins et les autres barrières ne sont pas chiffrés dans les textes du jeu → valeur type
(15 % des PV max, 60 % de l'attaque ou 80 % de la défense), marquée `estimated`.

## Combat (`calc/battle.py`)
1 à 4 héros par équipe, jauge de combat selon la vitesse. Compétences actives seulement (S1 et
compétences avec recharge) : soin prioritaire si un allié est sous 50 % de PV, sinon S3, S2,
S1 ; une compétence de soutien n'est jouée que si elle sert. Recharges réelles, sinon S2 = 3 et
S3 = 4 tours. Cible aux PV les plus bas (hors camouflage, ou le provocateur).
Effets appliqués : soins (bloqués par l'anti-soin), barrières (absorbent avant les PV), buffs
(attaque +50 %, défense +60 %, vitesse +30 %, critique +30 %, dégâts critiques +50 %,
immunité, invincibilité, camouflage, immortalité), débuffs (défense −70 %, attaque −50 %,
vitesse −30 %, étourdissement, sommeil, silence, provocation, anti-soin) avec chance de
réussite × (1 − (résistance − efficacité)), au moins 15 %, jauge ±, retrait de buffs et de
débuffs. Durées décomptées à la fin du tour du porteur (pas le tour où l'effet est reçu).
Taux de victoire sur des milliers de combats (graine fixe), bilan moyen (soins, barrières,
buffs, débuffs) et journal d'un combat type.
**Non simulés** : passifs et déclencheurs (contre-attaques, attaques supplémentaires,
résurrection), dégâts fixes, artefacts, esquive, âme brûlée, mécaniques propres à un héros.
