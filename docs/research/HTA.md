# Héritage des temps anciens (HTA / Ancient Inheritance) — recherche et pistes pour Zealot

État : note de recherche (octobre 2026). Rien n'est implémenté.

## 1. Ce qu'est le contenu

- **Exploration de guilde saisonnière** : Guilde › Champ de bataille › Héritage des temps anciens.
  Depuis 2021, environ 16 saisons (la saison 16 date d'avril 2026).
- **Conditions** (saison 2, peuvent avoir changé) : guilde de 16 membres ou plus, rang de compte 40.
  Quitter la guilde en cours de saison fait perdre sa progression et ses monnaies d'échange.
- **Carte à étages** (3 étages environ) : chaque joueur déplace son groupe sur des cases et combat
  des monstres, des élites et des **boss d'étage**. Le boss final s'appelle Frongo/Prongo selon
  la saison. Le premier étage nettoyé par la guilde ouvre le suivant.
- **Héros enrôlés** : le joueur enrôle une sélection de héros pour toute la saison. Le nombre de
  **retraits** (remplacements) est limité et l'interface le rappelle. Le choix des héros est
  donc l'enjeu principal.
- **Rations / provisions** : elles servent à se déplacer et à utiliser les objets de la carte.
  Elles se rechargent chaque jour, s'obtiennent aussi en montant de niveau d'exploration et dans
  les camps.
- **Niveau d'exploration et améliorations élémentaires** : depuis la saison 8, les améliorations
  de classe sont remplacées par des améliorations par élément. Vaincre un monstre donne de l'XP
  liée à l'élément qui lui est fort. Le conseil courant : un seul élément principal (feu, terre
  ou glace) monté au niveau 10, puis des spécialistes lumière/ténèbres pour les boss.
- **Reliques** : bonus passifs tirés des reliquaires (exemple : « Journal de l'équipe
  d'exploration »). Les reliques rares deviennent plus fréquentes avec le niveau d'exploration.
- **Objets de carte** : statues de soin (soignent les héros entre les combats), sacs
  d'exploration (XP et récompenses), menhirs de téléportation, pierres de vagabondage
  (téléportation sans retour possible), coffres personnels, coffres de guilde et coffres de
  guilde majeurs. Il existe aussi un événement « Parchemins de l'inconnu ».
- **Outils de guilde intégrés au jeu** : un tableau d'affichage (capitaine et vice-capitaines,
  5 à 380 caractères) et des mémos sur la carte (8 par étage, 20 caractères). Un classement
  affiche les 10 premières guildes à conquérir chaque zone.
- **Récompenses** : du matériel des boss, des coffres, et des **morceaux de rêve ancien** à
  échanger au bureau de change. Celui-ci ferme une semaine après la fin de l'exploration.

## 2. Le but pour le joueur

Gagner ensemble le plus de coffres de guilde et de boss d'étage, et viser le classement. Les
leviers sont les suivants :
1. bien choisir ses héros (les retraits sont rares) ;
2. se répartir les éléments dans la guilde ;
3. dépenser ses rations sans en gaspiller ;
4. bien choisir ses reliques.

## 3. Guides et outils existants dans la communauté

- Tableaux Miro de sélection des unités, classées par priorité : double attaquant, DPS, support,
  soigneur, plus une colonne « solo ». Les mêmes auteurs tiennent une base Google Sheets.
- Listes de héros par élément (Vortex Gaming, saison 13), listes de reliques (vidéos), guides
  FR (e7pourlesnoobs, chaîne @shurikn123 : « Quels teams ? », guides Jour 1 et Jour 3).
- Structure d'équipe conseillée contre les boss : 1 ou 2 doubles attaquants, 1 support,
  1 soigneur ou un 2ᵉ DPS, et une place libre selon le boss.
- **Il n'existe pas d'outil dédié** de planification d'équipe ou de coordination : tout passe
  par Miro, Sheets et Discord. C'est la place que Zealot peut prendre.

## 4. Ce que Zealot peut implanter (règles de `docs/COMPLIANCE.md` respectées)

Zealot a déjà les rosters des membres (`.e7v`), la guilde (`app/guild.py`), le module GvG
(`app/gvg.py`, à reprendre comme modèle), les simulateurs (`calc/`) et le partage Discord.

| Priorité | Fonction | Contenu | Réutilise |
|---|---|---|---|
| P1 | **Préparateur d'enrôlement** | Proposer, dans le roster du joueur, les héros de l'élément choisi, classés par rôle (double attaque, DPS, support, soin) et selon l'équipement réel (vitesse, PV, gear score). | `Roster`, `calc/gear_score`, `reference` |
| P1 | **Répartition des éléments dans la guilde** | Chaque membre déclare son élément principal et ses spécialistes lumière/ténèbres. Un tableau signale les éléments sans joueur. | `GuildStore`, modèle `gvg.json` → `hta.json` |
| P2 | **Tier list HTA locale** | Ajouter dans `data/reference/` un fichier `hta_tiers.json` (rôle, colonne « solo », saison), modifiable par la guilde. Les données sont écrites par nous, aucun asset du jeu n'est copié. | `e7-reference-data` |
| P2 | **Fiche d'équipe contre un boss** | Une composition par boss d'étage, avec les mécaniques notées. Option : estimation des dégâts avec le simulateur. | `calc/battle`, `calc/damage` |
| P2 | **Tableau de bord de saison** | Étage en cours, boss tués, retraits restants par joueur, rations du jour, date de fermeture du bureau de change. Tout est saisi à la main. | modèle GvG |
| P3 | **Publication Discord** | Envoyer à la guilde la carte « répartition et équipes » en PNG par webhook. Ce partage complète le tableau d'affichage du jeu, limité à 380 caractères. | `render/`, `publish/` |
| P3 | **Mémo des reliques** | Liste des reliques et note personnelle de priorité, saisies par l'utilisateur. | — |
| P4 | Lecture d'une capture de la liste des héros enrôlés (OCR) | Uniquement sur une capture d'écran importée, comme pour les héros. | `scanner/`, `vision/` |

**Ce qui est exclu** : lire l'état de la carte ou des rations dans la mémoire ou sur le réseau,
et automatiser les déplacements ou les combats (règle 1). Intégrer les cartes ou les icônes de
l'HTA est aussi exclu : l'exception de la règle 2 couvre seulement les deux décors GvG. Toutes
les données de saison restent saisies ou importées par le joueur.

**Format** : un nouveau fichier `hta.json` local n'a aucun effet sur `Roster` ni sur `.e7v`. Si
l'on veut partager le plan dans un `.e7v`, il faudra incrémenter `vitrine_file.VERSION` (règle 5).

**Première étape conseillée** : faire passer le P1 par l'agent `e7-architect`. Il s'agit d'un
écran « HTA » dans `ui.html` et d'un `app/hta.py` sur le modèle de `gvg.py`.

## Sources

- https://www.mumuplayer.com/m/fr/blog/saison2-hta-epic-seven.html
- https://epic7x.com/12-5-update-ancient-inheritance-and-fire-adin/
- https://projectavinoc.com/epicseven/guides/ancient-inheritance-primer/
- https://vortexgaming.io/en/postdetail/544193
- https://epic7guides.com/guides/unlocking-the-mysteries-of-ancient-inheritance/
- https://www.e7pourlesnoobs.com/
- https://www.youtube.com/watch?v=-qYZyJeniUA (lien Miro et Google Sheets dans la description)
