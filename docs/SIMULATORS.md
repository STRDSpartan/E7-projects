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
### Passifs et contre-attaques
`parsers/skill_effects.parse_trigger` lit le déclencheur de chaque passif (champ `trigger`) :
`battle_start` (début de combat), `turn_start` / `turn_end` (tour du porteur), `attacked` (après
avoir été attaqué), `after_attack` (après avoir attaqué : attaque supplémentaire si le passif
inflige des dégâts), `revive` (résurrection une fois par combat, PV du texte) et `counter`
(« X % de chances de contre-attaquer »). Chance et « une fois tous les N tours » sont respectées.
Événements aussi reconnus : allié attaqué, compétence ennemie (ou seulement non offensive),
début de tour ennemi, fin de tour d'un allié / d'un ennemi / de n'importe qui, mort d'un héros,
coup critique porté, dégâts mortels (ex. immortalité).
**Passifs à conditions** (`condition`) : PV du porteur ≤ X %, PV de la cible ≤ X %, PV pleins,
avec ou sans débuff, compétence ennemie non offensive.
**Jauges** (`resource`) : Concentration (pleine = 5) et Esprit combatif (plein = 100), remplies
du montant du texte par l'événement indiqué (« when an ally is attacked, gains 10 Fighting
Spirit »), valeur de départ comprise (« starts the first battle with 50 ») ; le passif se joue
et vide la jauge quand elle est pleine. Sans gain écrit : +1 Concentration par tour, +10 Esprit
par attaque subie (`estimated`). ~185 des 264 passifs ont un déclencheur reconnu.
Les effets du passif (`effects`) sont joués au déclenchement.
Contre-attaque : passif ou **set Contre** (30 %), après une attaque subie pendant le tour de
l'adversaire, sauf étourdi ou endormi ; frappe avec la compétence du passif si elle a un taux,
sinon S1 ; pas de contre-attaque d'une contre-attaque. Le journal les affiche sous l'action
(« ↳ »), le bilan moyen compte contre-attaques et passifs déclenchés.

### Mécaniques propres aux héros
Lues dans les étiquettes E7GW de chaque compétence (`parse_effects`) :
- **tour supplémentaire** (toujours, sur chance, ou si la cible meurt ; pas celui de l'âme
  brûlée) et **attaque double** (S1 de l'allié à la plus forte attaque) ;
- **recharges** : réduction sur soi (−N tours, remise à zéro) et augmentation chez l'ennemi ;
  recharge pleine au départ (« Begins Battle With Full Skill Cooldown ») ;
- **brûlure** (60 % de l'attaque du lanceur), **saignement** (30 %), **poison** (5 % des PV
  max), au début du tour du porteur, sans défense (valeurs communautaires approchées) ;
- **esquive +** et **précision −** : 50 % de coups ratés (dégâts × 0,75) ;
- **attaque ++** (+75 %), **annulation** (le prochain coup ne fait rien), **buffs interdits** ;
- **vol de vie** de la compétence (taux du texte, sinon 20 % estimé) et **set Vampire** (20 %) ;
- **critique garanti** ; **réduction de dégâts** permanente et **plafond de dégâts par coup**
  (« does not exceed 35% of max Health ») des passifs.

- **Âmes et âme brûlée** : chaque équipe gagne 1 Âme par S1 et 2 par autre compétence
  (estimé, max 20) ; une S2/S3 qui a une version âme brûlée la joue dès que l'équipe a le coût
  (« -10 souls » du texte, sinon 20) ;
- **blessures** : PV max réduits de 25 % des dégâts (estimé), jusqu'au plafond du texte
  (« up to 15% injuries ») ; les soins ne dépassent pas les PV max blessés ;
- **explosion** : les tours restants de brûlure / saignement infligent leurs dégâts d'un coup ;
- **extinction** : la cible tuée ne peut plus ressusciter ;
- **dégâts fixes** (« 1,500 fixed damage », par débuff ou sur critique), sans défense ;
- **rang arrière** : le dernier héros de l'équipe ;
- **insensible aux débuffs d'immobilisation** (étourdissement, sommeil).

Correction : un buff n'est plus jamais appliqué aux ennemis (« attaque tous les ennemis et
augmente l'Attaque » visait les ennemis, ex. Arbiter Vildred S3).

### Règles par héros (`data/reference/hero_mechanics.json`)
Ce que les textes ne permettent pas de déduire s'ajoute héros par héros, sans toucher au
moteur. Clé = clé du héros dans `skills.json` ; par compétence : `set` (champs remplacés :
`trigger`, `no_crit`, `aoe`...), `effects` (liste remplacée), `effects_add` (effets ajoutés),
et obligatoirement `source` (le texte du jeu traduit). Effets disponibles :
`calc/battle.EFFECT_TYPES`, dont `static_buff` / `static_debuff` / `static_immune` (statuts
permanents). Un test vérifie chaque règle (héros existant, types connus, source présente).
Exemples : Aki (ne peut pas être soignée), Schuri Exécuteur du Vent d'Ouest (pas de critique).

Définitions des effets : infobulles officielles des pages E7GW (`data-fx-desc`). Elles fixent
saignement (40 % de l'attaque) et brûlure (70 %) en ignorant 70 % de la défense, venin (10 % des
PV max + blessures), peur (pas d'action, 40 % de chances de disparaître au début du tour),
entrave (ni contre-attaque, ni attaque double, ni attaque supplémentaire hors de son tour),
sceau (passifs inactifs), rupture (dégâts additionnels ∝ PV max, part estimée à 5 %),
surhumanisation (PV max et vitesse +100 %), indomptable (défense et résistance +30 %), moral
(+10 % de dégâts), efficacité + (+50), posture féroce (seul le porteur peut être ciblé),
offrande (70 % de partage des dégâts des alliés, immortalité une fois), abondance (+2 000
dégâts après une attaque), partage de dégâts. Autres nouveautés du moteur : attaques sur
plusieurs cibles, résurrection d'un allié, événements « début du tour d'un allié » et « âme
brûlée utilisée », conditions de position (premier emplacement) et de buff, jauges à coût
partiel, contre-attaque quand un allié est attaqué, dégâts doublés hors de son tour.

#### Lots de héros (classement RTA Champion+, epic7rtastats.com, 3–10 oct. 2026)
- **Lot 1** (fait) : School Nurse Yulha, Estelle, Rhianna and Luciella, Boss Arunka, Lady of
  the Scales, Arbiter Vildred, Shepherd of the Dark Diene, Perfumer Byblis, Haru, Kawerik.
  Non simulés pour eux : l'érosion de Rhianna (non définie par E7GW), le parfum persistant de
  Byblis, la recopie de jauge de la Dame de la Balance, le seuil « 20 % des PV » de la
  contre-attaque d'Estelle, les gains d'attaque ∝ PV de l'infirmière Yulha ; montants de soin
  non chiffrés par le jeu marqués `estimated`.
- **Lot 2** (fait) : Zio, Renoa, Eye of the Abyss Fumyr, Belian, Monarch of the Sword Iseria,
  Notos, Tidal Rift Elvira, Rinak, Frieren, Aubade Ludwig. Mécaniques ajoutées (définitions
  E7GW) : attaques supplémentaires conditionnelles (`extra_attack` : chance, pendant son tour,
  une fois par tour, si un buff est actif, effets si la cible meurt), déification (critique
  +50 %, dégâts subis −50 %), Dieu de la guerre (stats doublées) et Sanctuaire (aucun buff ni
  débuff), marques cumulables Fracture / Butin / Pillage, balles funèbres de Renoa, détention
  (retiré du combat), malédiction (60 % des dégâts des alliés), engloutissement et cascade
  (+4 000 dégâts fixes), aube (Âmes ×2, 25 % d'étourdir), magie défensive (4 Âmes pour annuler
  un coup), blocage, soin continu (15 % des PV max), buff aléatoire, dégâts fixes de zone,
  insensible aux Âmes ennemies, jauge figée, contre-attaques doublées et en chaîne.
  Estimations : une attaque par balle funèbre (5 au plus) avec les multiplicateurs de la S1,
  1 000 dégâts par Âme consommée (Lumière de la condamnation), recharges par défaut des S3 de
  Renoa et Iseria, barrières non chiffrées. Non simulés : jauge recopiée par Elvira après les
  compétences alliées, dégâts ∝ PV de la cible de Zio, ressources +40 % de Frieren.
- **Correction** : Critique + vaut +50 % (infobulle officielle), et l'insensibilité aux
  débuffs d'immobilisation couvre aussi la peur.
- **Lot 3** (à faire) : héros suivants du classement RTA.

**Non simulés** : mécaniques uniques non encore décrites dans `hero_mechanics.json` (balles de
Renoa, vitesse fixe de Harsetti, marques...), Bombes, partage de dégâts, transferts, artefacts,
bonus de stats permanents des passifs (déjà inclus dans les stats affichées en jeu).
