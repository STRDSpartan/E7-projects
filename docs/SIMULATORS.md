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

## Combat (`calc/battle.py`)
Modèle simplifié, 1 à 4 héros par équipe : jauge de combat selon la vitesse, S3 puis S2 puis S1
selon les temps de recharge (S2 = 3, S3 = 4 tours par défaut, modifiables), cible aux PV les plus
bas, compétences de zone sur toute l'équipe, critiques tirés au hasard. Des milliers de combats
(graine fixe) donnent un taux de victoire reproductible et le journal d'un combat type.
**Non simulés** : soins, barrières, buffs/débuffs appliqués par les compétences, passifs,
artefacts, esquive, contre-attaques, gain/vol de jauge. C'est un ordre de grandeur.
