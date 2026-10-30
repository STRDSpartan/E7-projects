# Epic Seven sur Steam — ce que ça change (ou non) pour Zealot

État : note de recherche (30 octobre 2026, au lendemain de la sortie). Rien n'est implémenté.

## 1. Les faits

| Point | Ce que disent les sources |
|---|---|
| Sortie | 28 ou 29 octobre 2026, selon le fuseau horaire (app Steam **5019180**, éditeur Smilegate). Jeu gratuit. Une démo était disponible pendant le Steam Next Fest (8-27 octobre). |
| Compte | **Compte tiers STOVE obligatoire** (« Supports Linking to Steam Account »). Un compte existant (e-mail, réseau social) passe en « Simple Login (Steam) » sans perte de progression. |
| Serveurs | Nouveau serveur **Foundry**, ouvert le même jour. Les joueurs Steam peuvent aussi jouer sur les serveurs existants. Cross-play et cross-progression avec STOVE PC et mobile. |
| Fonctions Steam déclarées | Solo, JcJ et coop en ligne, achats intégrés, sous-titres, réglage du volume, jouable à la souris seule, manette partielle (DualShock, DualSense), partage familial. |
| Fonctions **absentes** | **Aucun succès Steam**, aucune sauvegarde Steam Cloud, aucun Workshop, aucun inventaire ni économie Steam. L'API de la boutique (`appdetails`) ne renvoie aucun bloc `achievements`. |
| Anti-triche | « Uses Kernel Level Anti-Cheat » : **UNCHEATER**, au niveau du noyau. |
| Plateforme | Windows 10 64 bits uniquement. Le Steam Deck est un objectif, sans date. |
| Accueil | Avis « mitigés » (52 % positifs sur 328) au moment de la recherche. |

## 2. L'API Steam peut-elle aider Zealot ?

**Non, pas pour l'essentiel.** L'API Web Steam ne connaît que ce que le jeu lui transmet :
possession du jeu, temps de jeu, succès, statistiques et objets d'inventaire Steam. Epic Seven
sur Steam n'utilise rien de tout cela. Les héros, l'équipement, la guilde et l'Arène sont
stockés sur les serveurs de Smilegate et liés au compte **STOVE**. Steam ne sert ici que de
boutique, de lanceur et de moyen de connexion.

- Aucune donnée de roster ni d'équipement n'est lisible par l'API Steam, que l'on ait une clé
  publique ou un jeton OAuth.
- Tout ce qu'on pourrait afficher : le pseudo et l'avatar Steam du joueur, son temps de jeu
  sur Epic Seven. Cela demanderait une clé d'API et un profil public, pour une valeur quasi
  nulle par rapport à la fiche de profil du jeu, que Zealot lit déjà.
- Pas d'API publique côté STOVE ou Smilegate pour les données de jeu. Les intercepter
  violerait la règle 1 de `docs/COMPLIANCE.md`, Steam ou non.

## 3. Ce que la version Steam change réellement

### Bonnes nouvelles
1. **Captures Steam (F12).** Steam enregistre les captures du jeu dans un dossier connu, en
   principe `<Steam>/userdata/<id>/760/remote/5019180/screenshots/` (chemin à confirmer sur une
   installation réelle). Une option de Steam garde aussi une copie non compressée dans le
   dossier de son choix. Zealot pourrait **surveiller ce dossier** et proposer d'importer les
   nouvelles captures. Le parcours deviendrait : F12 sur chaque fiche de héros, puis
   « Importer les captures Steam ». C'est le gain le plus concret, et il reste dans les règles
   (le joueur prend lui-même les captures, rien n'est lu dans le client).
2. **Public élargi.** De nouveaux joueurs arrivent, sur un nouveau serveur, avec des
   événements de croissance (20 invocations par jour). La demande d'outils (vitrine, équipe,
   GvG, HTA) augmente. Les guides et le hub communautaire Steam sont un canal possible pour
   présenter Zealot.
3. **Même client, même interface.** Le jeu sur Steam est le client PC, avec un compte partagé.
   Le moteur de reconnaissance et ses zones normalisées devraient continuer de fonctionner.
   À vérifier sur une capture réelle du client Steam (voir la skill `calibrate-ocr-regions`).

### Points de vigilance
1. **Anti-triche au niveau du noyau (UNCHEATER).** Il peut empêcher la capture de la fenêtre
   (image noire avec `mss`/BitBlt si la fenêtre est exclue de la capture) et pourrait signaler
   des clics automatisés. Conséquences :
   - garder l'import de captures comme parcours principal ;
   - tester le scan en direct (`capture/`) sur le client Steam avant de le promettre ;
   - laisser `AssistedNavigator` désactivé par défaut et déconseiller son usage avec le client
     Steam tant que la tolérance de l'anti-triche n'est pas connue. Smilegate ne publie aucune
     règle sur les outils tiers.
2. **Serveur « Foundry » inconnu de Zealot.** `parsers/profile_card.py` ne reconnaît que
   Europe, Global, Asie, Corée et Japon. Une fiche de profil Foundry est lue sans serveur. Il
   faut ajouter ce serveur (libellé français exact à relever sur une capture : « Foundry » ou
   une traduction).
3. **Fenêtre du jeu.** `capture/window.py` cherche une fenêtre dont le titre contient
   « Epic Seven ». C'est probablement aussi le cas sur Steam, mais à vérifier. Le lanceur
   STOVE peut encore s'intercaler.
4. **Steam Deck et Linux.** Ils ne sont pas pris en charge pour l'instant, et l'anti-triche du
   noyau rend Proton incertain. L'import de captures de Zealot fonctionne de toute façon sur
   n'importe quel système.

## 4. Recommandations pour Zealot

| Priorité | Action | Coût |
|---|---|---|
| P1 | Ajouter le serveur **Foundry** au parseur de la fiche de profil (`SERVERS`) et l'afficher | très faible |
| P1 | Valider le moteur sur des **captures du client Steam** (fiche héros, liste, profil) | faible, captures à fournir |
| P2 | **Import depuis le dossier de captures Steam** : détecter `userdata/*/760/remote/5019180/screenshots`, lister les nouvelles captures et les importer d'un clic | moyen |
| P2 | Tester le **scan en direct** et la capture de fenêtre avec l'anti-triche ; documenter le résultat dans `docs/COMPLIANCE.md` | faible |
| — | API Web Steam | aucun intérêt pour les données de jeu, à ne pas faire |

En bref : **la version Steam ne donne accès à aucune donnée de jeu exploitable** (pas de succès
ni d'inventaire Steam, compte STOVE derrière). Elle change surtout le **public** et ajoute un
**raccourci de capture** (F12, dossier connu), que Zealot peut exploiter sans enfreindre ses
règles. L'anti-triche du noyau est un argument de plus pour le parcours par captures plutôt que
pour le scan en direct.

## Sources
- https://store.steampowered.com/app/5019180/Epic_Seven/ et l'API `appdetails` de la boutique
- https://steamdb.info/app/5019180/
- https://www.invenglobal.com/articles/26951/epic-seven-officially-launches-on-steam-oct-29-opens-new-server
- https://www.invenglobal.com/articles/27936/epic-seven-officially-launches-on-steam-opens-new-server-foundry
- https://noisypixel.net/epic-seven-steam-launch-foundry-server-demo/
- https://noisypixel.net/epic-seven-steam-cross-play-progress-transfer/
- https://finalweapon.net/2026/10/08/epic-seven-steam-release/
- https://gachago.com/en/news/epic-seven-steam-launch-october-29-foundry-server
- https://epic-seven.wiki/updates/steam/ (site communautaire, non officiel)
- https://www.hideoutgacha.com/news/epic-seven/steam-store-page-open
- https://store.steampowered.com/app/5129800/Epic_Seven_Demo/
