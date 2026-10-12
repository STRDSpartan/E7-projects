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
- **Lot 3** (fait, page /heroes d'epic7rtastats : taux de pick/ban, saison d'automne 2026,
  héros 3 à 30 non encore traités) : Lisette, Harsetti, Hecate, Salome, Briar Witch Iseria,
  Genesis Ras, New Moon Luna, Moon Bunny Dominiel, Aube, Disciplinary Prefect Aria.
  Mécaniques ajoutées : loi de Skuggiheim (vitesse figée, autres limités à 90 %, pas de gain
  de jauge pendant le tour d'Harsetti), interdiction de résurrection et d'immortalité,
  Divinité (insensible aux débuffs, PV et défense +20 % par marque) et résurrection d'un allié
  mort, Effondrement (PV max −50 % sur un héros), Pacte sacré, annulation d'effet,
  Immobilisation, Restriction, Dissimulation, Vigueur (+30 % attaque et défense), durée des
  buffs réduite, tour supplémentaire sur critique, événement « tour supplémentaire ennemi »,
  attaque supplémentaire si une compétence est en recharge, aura de résistance, coût d'âme
  brûlée doublé. Non simulés : clonage de Salome, retour temporel de Lisette (PvP), dégâts de
  zone additionnels de Luna, pénétration cumulable d'Aria.
- **Corrections générales** (infobulles officielles) : le sommeil se dissipe quand on subit des
  dégâts ; le camouflage réduit de 50 % les dégâts de zone puis disparaît.
- **Lot 4** (fait, rangs 31 à 40) : Tactical Archetype Coli, Desert Jewel Basar, Schniel,
  Setsuka, Empyrean Ilynav, Lone Crescent Bellona, Little Queen Charlotte, Ivana, Uncharted
  Pioneer Politis. Silvertide Christy n'a pas de multiplicateurs (absente d'E7Calc) : non
  simulable. Mécaniques ajoutées : Bombe (150 % de l'attaque, 70 % de défense ignorée, puis
  immobile 1 tour), Surcharge (+50 % attaque et vitesse) puis Épuisement, Attaque rapide (+50 %
  de jauge en fin de tour), Inversion de barrière, Envoûtement (10 % des PV max des alliés du
  porteur), Rayonnement (dégâts −50 %), aura d'esquive et contre-attaque quand un allié esquive,
  réduction des dégâts critiques, Savoir des étoiles (dégâts additionnels ×2), missions de
  Politis (10 attaques alliées ou 10 attaques subies), cumul d'attaque de Bellona, retrait
  ciblé d'un buff (immortalité), jauge jamais diminuée, événements « allié utilise une attaque
  sur une cible », « attaque de l'équipe », « allié esquive », « critique subi ». Non simulés :
  consommation des PV de Setsuka, cumul des dégâts fixes de Schniel, bonus anti-Ténèbres de
  Charlotte, bonus de stats des missions de Politis.
- **Lot 5** (fait, rangs 41 à 75, 35 héros) : Spirit Eye Celine, Ruele of Light, Vildred,
  Mort, Successor Taeyou, Dark Corvus, Witch of the Mere Tenebria, Saria, Young Senya, Tori,
  Lidica, Aram, Celine, Frida, Sea Phantom Politis, Swift Flagbearer Sigret, Infinite Horizon
  Achates, Faithless Lidica, Elena, Maid Chloe, Commander Pavel, Afternoon Soak Flan, Straze,
  Lionheart Cermia, Bystander Hwayoung, Argent Waves Hwayoung, Wanderer Silk, Aki, Festive Eda,
  Blooming Lidica, Amid, Lone Wolf Peira, Chaos Sect Axe, Urban Shadow Choux, Pirate Captain
  Flan. Mécaniques ajoutées : Possession (+25 % d'attaque, contre-attaque sur critique subi),
  Rage, Saccage, Cible (+15 % de dégâts reçus), buffs Résurrection (30 %) et Protection du
  Seigneur des esprits (50 %, jauge +50 %), Limite de dégâts (35 %), Amitié spéciale, Bzzt!,
  âme brûlée offerte, débuff aléatoire, vol de buff, assistance des alliés, compétence
  remplacée pendant son tour (`swap`), résurrection de tous les alliés, buffs indissipables,
  insensibilité aux buffs et débuffs, interdiction de contre-attaquer (Mort), compétences sans
  contre-attaque, jauge par cible touchée, Esprit combatif tiré de la jauge ennemie (Taeyou),
  Âmes gagnées, conditions d'effet (buff du lanceur, débuff de la cible, critique, recharge),
  nouveaux événements (ennemi vaincu, critique allié, tour supplémentaire allié, compétence de
  base alliée, compétence non offensive alliée, attaque de zone subie, attaque alliée).
  Estimations et limites : PV des résurrections non chiffrés, chance moyenne de Cascade de
  Tori, déclencheurs de Lionheart Cermia et de Mort approchés ; non simulés : réduction de
  ressources (Lidica, Sea Phantom Politis), premier tour d'Aram, riposte Sura de Bystander
  Hwayoung, saccage réservé aux héros Ténèbres (donné à tous).
- **Correction** : Dégâts critiques + vaut +70 % (infobulle officielle).
- **Lot 6** (fait, rangs 76 à 105 — le site ne publie pas au-delà) : Politis, Sage Baal &
  Sezan, Inheritor Amiki, Requiem Roana, Unbound Knight Arowell, Elvira, Schuri, Veronica,
  Summer Break Charlotte, Top Model Luluca, Fallen Cecilia, Silver Blade Aramintha, Midnight
  Gala Lilias, Sinful Angelica, Abyssal Yufine, Dragon King Sharun, Diene, Jenua, Designer
  Lilibet, Yulha, Fenris, Lilias, Death Dealer Ray, Surin, Westwind Executioner Schuri, Twisted
  Eidolon Kayron, Dragon Bride Senya, Last Rider Krau, Zeno. Mei Lin n'a pas de multiplicateurs
  (absente d'E7Calc) : non simulable. Mécaniques ajoutées : Escorte (40 % de partage), Explosifs,
  Serment de punition (insensible aux débuffs, 2 500 dégâts fixes), Pestilence, Traumatisme
  (défense −70 %, attaque et vitesse ×2), Attaque double renforcée, posture de contre-attaque,
  débuff de classe (classe du héros ajoutée au combattant), renvoi de dégâts, réduction des
  dégâts additionnels et fixes, réduction des gains de jauge ennemis (compétences et vitesse),
  transfert de débuffs, allongement / raccourcissement des débuffs, résurrection interdite aux
  ennemis, critique garanti selon la Concentration (Schuri), compétence remplacée selon une
  recharge ou un débuff. Non simulés : Morsure de Jenua et cumuls de Zeno (multiplicateurs
  inconnus), dégâts de zone additionnels non chiffrés (Amiki, Jenua), bonus d'Esprit de Kayron ;
  déclencheurs approchés pour Fenris et Arowell (toute attaque subie par un allié).
- **Mécaniques manquantes intégrées** (v0.19.0) : l'extracteur E7Calc lit désormais les
  dégâts additionnels (`aftermath` : statistique × part × 1,871, 70 % de défense ignorée), perdus
  jusque-là pour 23 compétences (Monarch of the Sword Iseria, Salome, Requiem Roana, Lone Wolf
  Peira, Festive Eda, Senya, Sol, AE Karina, Albedo...) ; dégâts de zone additionnels de Luna,
  Little Queen Charlotte (contre les Ténèbres, dégâts +35 %), Jenua (sur critique), Inheritor
  Amiki, Sez (si la cible meurt), Notos (sous Dieu de la guerre). Formules dynamiques E7Calc
  (`dynamic`) : PV actuels de la cible (Zio), PV perdus de la cible (Frieren), écart de PV
  (Fenris), PV perdus du lanceur et PV consommés (Setsuka), pénétration sous 30 % des PV (Amiki)
  ou cumulable (Aria), élément de la cible (Bystander Hwayoung ×2 contre la Lumière). Aussi :
  Bête ancestrale de Zeno (cumuls), Esprit combatif consommé par Kayron (+100 par point), dégâts
  fixes croissants de Schniel, attaque ∝ PV de l'infirmière Yulha (8 %), résistance ∝ PV d'Aria,
  seuils de dégâts subis (Estelle 20 %, riposte Sura de Bystander Hwayoung 40 %), recopie de jauge
  de la Dame de la Balance (50 %) et de Tidal Rift Elvira (25 % par débuff infligé), ressources
  +40 % (Frieren), −60 % (Lidica, durée estimée à 2 tours) et −50 % (Sea Phantom Politis),
  missions de Politis (attaque ou PV max +10 %), premier tour d'Aram, Saccage réservé aux
  Ténèbres, Morsure de Jenua (multiplicateurs de la S1, estimés), clone de Salome (compétences du
  héros le plus offensif, estimé), retour temporel de Lisette (PV et débuffs remis à zéro à la
  mort), déclencheurs exacts de Fenris (attaque supplémentaire, double ou contre-attaque subie
  par un allié) et d'Arowell (attaque à cible unique). Non définis par le jeu, donc estimés :
  érosion de Rhianna (comme un saignement, explosée sur critique) et parfum persistant de Byblis
  (dégâts subis −15 %). Mei Lin et Silvertide Christy, absentes d'E7Calc,
  ont une fiche **estimée** (clé `hero` dans `hero_mechanics.json` : élément, classe, stats de
  base) : Mei Lin S1 taux 1,0 (critique garanti, jauge +20 %, recharges −1), S2 taux 1,3
  (critique garanti, extinction), S3 soin complet + tour supplémentaire, attaque et défense
  égalisées ; Silvertide Christy S1 taux 0,7 + 12 % des PV max (provocation 75 %), S2 jauge +20 %
  pour elle et le rang arrière après une attaque subie sans débuff, S3 attaque + des alliés et
  soin de 15 % (estimé). Mei Lin : Zèle gagné quand un allié Feu utilise une compétence
  (2 cumuls, S2 +25 % par cumul, estimé, retiré après la S2) et attaque suivant la S3 rejouée.
  Christy donne au départ 50 % de sa résistance à l'allié du rang arrière (sauf si elle y est),
  perdue définitivement à la mort de cet allié, y compris s'il se relève sur place
  (buff Résurrection, Pacte sacré, passif de résurrection ; l'immortalité n'est pas une mort).
- **Suite** : le classement public d'epic7rtastats s'arrête au rang 105 (filtre « Remove Low
  Pick Data ») ; les héros restants pourront suivre par listes fournies.

**Non simulés** : mécaniques uniques non encore décrites dans `hero_mechanics.json` (balles de
Renoa, vitesse fixe de Harsetti, marques...), Bombes, partage de dégâts, transferts, artefacts,
bonus de stats permanents des passifs (déjà inclus dans les stats affichées en jeu).
