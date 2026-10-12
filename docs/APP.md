# Application de bureau E7 Showcase

Application téléchargeable : le joueur crée son **profil**, y glisse les **captures d'écran** de ses
héros, consulte sa **vitrine** et l'**exporte** en un fichier `.e7v` que n'importe qui ouvre avec
la même application sur son ordinateur.

## Parcours
1. *Nouveau profil* → nom du joueur.
2. Glisser les captures (PNG/JPG/WebP, « Impr. écran » brutes acceptées) :
   - **Infos de héros** → héros complet (stats, 6 pièces, sets, artefact, empreinte, puissance)
     + **pose du personnage** recadrée sur la capture (image du héros dans la vitrine) ;
   - **liste des héros** → blasons des sets portés (appris une fois pour toutes) ;
   - **catalogue des sets** (filtre d'inventaire) → les 24 blasons.
   Facultatif : les blasons de référence des 24 sets sont téléchargés automatiquement au
   premier import (connexion Internet nécessaire une fois).
3. La vitrine se construit : recherche, filtres (élément, classe, set), tris, fiche détaillée.
4. *Exporter la vitrine* → `vitrine-<joueur>.e7v`. *Exporter en tableur (.csv)* →
   `vitrine-<joueur>.csv`, tout le profil dans un seul fichier : résumé du profil, héros (stats)
   et armurerie (pièces portées et non équipées) — `GET /api/profiles/<id>/csv`.
5. Le destinataire : double-clic sur le fichier (association installée) ou *Ouvrir une vitrine* →
   rangée dans « Vitrines reçues », consultation seule.

## Onglets
- **Vitrine** : le profil choisi à gauche (import des captures, export `.e7v`).
- **Simulateur de combat** : combat entre deux équipes et calcul des dégâts.
- **Guilde** : nom de la guilde et membres (son profil + les vitrines `.e7v` reçues des
  coéquipiers) avec héros, puissance cumulée, pièces et héros les plus puissants ; accès direct à
  la vitrine et à l'armurerie de chacun. Stockage local : `<données>/guild.json`.
  Bouton « Exporter les membres (.csv) » (`GET /api/guild/csv`) : un membre par ligne
  (origine, héros, puissance, pièces, héros les plus puissants, mise à jour). Bouton « Exporter
  toute la guilde (.csv) » (`GET /api/guild/full.csv`) : un seul fichier avec les membres, les
  héros et l'armurerie de chacun (colonne « Membre »), puis les défenses GvG, les contres connus
  et le suivi des guerres. Bouton « Importer toute la guilde (.csv) » (`POST /api/guild/import`,
  `app/guild_import.py`) : relit ce fichier sur un autre ordinateur. Chaque membre est rapproché
  d'un profil par son nom : vitrine reçue mise à jour (héros, armurerie), ou créée si absente ;
  les profils du joueur lui-même ne sont jamais écrasés. Les défenses sont replacées et les
  guerres absentes (même adversaire, même date) recréées avec leurs attaques ; contres et
  attaques restantes s'en déduisent. Les icônes des objets et les portraits ne sont pas dans le
  CSV (seulement dans les `.e7v`).
- **Armurerie** : toutes les pièces du profil choisi. Les pièces **portées** viennent des fiches
  « Infos de héros » (icône découpée sur la capture, set, rang, niveau, amélioration, stats) ; les
  pièces **non équipées** viennent de captures de l'infobulle d'un objet de l'inventaire, glissées
  comme les autres captures (`parsers/item_parser.py` lit l'emplacement, le rang, le set,
  l'amélioration, la stat principale et les stats secondaires ; la description du set est
  ignorée). L'**image de l'objet** est découpée sur la capture (`vision/item_icon.py`) : sa
  position est déduite des boîtes de texte de l'OCR (« +15 » dessiné sur l'icône, en-tête à sa
  droite) puis resserrée sur le cadre de l'icône ; à recalibrer sur de vraies captures
  d'infobulle. Les icônes voyagent dans le `.e7v` (`images/item-<id>.webp`). Filtres par emplacement, set, stat principale, état (de côté / portée), recherche et
  tris ; résumé des pièces de côté par set. Les pièces de côté sont rangées dans
  `Roster.inventory` (champ facultatif : les anciens profils et fichiers `.e7v` restent lisibles).
- **GvG** (`gvg.py`, stockage local `<données>/gvg.json`, API `/api/gvg`) :
  - *Défenses* : pour chaque membre de la guilde, la tour défendue et deux équipes de 3 héros
    choisis dans son roster (un héros ne défend que dans une équipe), enregistrées aussitôt ;
  - *Guerres* : guerre contre une guilde adverse (date), attaques enregistrées (attaquant, équipe
    utilisée, défense ennemie, joueur et tour adverses, victoire ou défaite, note), taux de
    victoire et attaques restantes par membre (nombre d'attaques par guerre réglable) ;
  - *Contres* : pour chaque défense ennemie rencontrée, les équipes qui l'ont battue ou non,
    cumulées sur toutes les guerres, avec recherche par héros.
  - *Export du plan de défense* (`GET /api/gvg/plan`) : par tour, les équipes de chaque membre
    et les membres sans défense ; texte prêt pour Discord, découpé en messages de moins de
    2 000 caractères (bouton « Copier »), ou fichier `.md` / `.csv` (séparateur « ; », formules
    neutralisées) ; le `.csv` ajoute le suivi des guerres (une ligne par attaque, puis les
    attaques restantes de chaque membre) ; le suivi seul s'exporte aussi depuis l'onglet
    Guerres (bouton « Exporter le suivi (.csv) », `GET /api/gvg/wars/csv`), et les contres connus seuls depuis l'onglet
    Contres (bouton « Exporter les contres (.csv) », `GET /api/gvg/counters/csv`), et les défenses seules depuis l'onglet
    Défenses (bouton « Exporter les défenses (.csv) », `GET /api/gvg/defense/csv`) ;
  - *Contres dans le plan* (case « Inclure les contres connus », réglage `plan_counters`) : le
    texte Discord, le fichier `.md` et le plan publié se terminent par les contres connus, et le
    `.csv` reçoit un second tableau sous les défenses (défense ennemie, équipe d'attaque,
    victoires, défaites, bilan) ; le
    plan publié en mise à jour automatique suit alors aussi chaque nouvelle attaque ;
  - *Publication sur Discord* : bouton « Envoyer sur Discord » (après confirmation) qui publie le
    plan dans le salon de la guilde par **webhook** (`publish/webhook.post_messages`, aucune
    mention déclenchée, limite de débit respectée). L'adresse du webhook, qui donne le droit
    d'écrire dans le salon, est validée (domaines Discord seulement), rangée dans
    `<données>/discord.json`, jamais renvoyée en clair à l'interface ni exportée dans un `.e7v` ;
  - *Mise à jour automatique* (case à cocher) : à chaque modification du plan (défenses, tours,
    nom ou membres de la guilde), le plan publié est **modifié dans Discord** 20 s après la
    dernière modification (les changements rapprochés sont regroupés), sans nouveau message ;
    un message supprimé à la main est republié, les messages en trop sont effacés. Une mise à
    jour en attente part à la fermeture de l'application ; la dernière publication (ou son
    erreur) est affichée ;
  - *Suivi des guerres sur Discord* (page Guerres, même webhook) : score, attaques (✅ / ❌,
    équipe, défense ennemie, joueur et tour, note) et attaques restantes de chaque membre
    (`gvg.war_report`, `POST /api/gvg/wars/<id>/send`). Option de mise à jour automatique
    (distincte de celle du plan) : le message de suivi déjà publié est modifié à chaque attaque
    enregistrée ou supprimée, 20 s après la dernière ; une guerre supprimée dans l'application
    laisse ses messages dans Discord. Publications et messages suivis : `discord.json`
    (`publications` : `plan`, `war:<id>`) ;
  - *Contres connus sur Discord* (page Contres, même webhook) : pour chaque défense ennemie, les
    équipes testées et leur bilan (✅ toujours gagnée, ⚖️ mitigée, ❌ perdue), toutes guerres
    confondues (`gvg.counters_report`, `POST /api/gvg/counters/send`) ; option de mise à jour
    automatique à chaque attaque enregistrée ou supprimée (publication `counters`) ;
  - *Tests dans le simulateur de combat* (500 combats) : une attaque saisie contre la défense
    ennemie notée, une équipe d'un membre contre une défense de l'onglet Contres, ou une défense
    de la guilde contre une attaque ennemie supposée. Les héros adverses, connus par leur seul
    nom, prennent les stats types d'un héros équipé pour le JcJ selon leur classe (signalés
    « estimé » ; `simulator.ESTIMATED_STATS`) ; les héros de la guilde gardent leurs vraies stats.

## Architecture (`src/e7showcase/app/`)
| Fichier | Rôle |
|---|---|
| `launcher.py` | point d'entrée `e7showcase-app [fichier.e7v]` : serveur local + fenêtre native (pywebview + WebView2), pas de version navigateur |
| `server.py` | serveur HTTP local (127.0.0.1, port aléatoire), API JSON, jeton de session + contrôle de l'en-tête Host ; import en arrière-plan suivi par `/api/jobs/<id>` (barre de progression) |
| `ui.html` | interface (HTML/JS sans dépendance) |
| `armory.py` | armurerie : pièces portées et non équipées d'un profil, blasons des sets (API `/api/profiles/<id>/armory`, `DELETE …/items/<id>`) |
| `gvg.py` | guerre de guilde : défenses, guerres, attaques, contres (API `/api/gvg`, `PUT /defense/<membre>`, `POST /wars`, `POST /wars/<id>/attacks`, `PATCH /settings`) |
| `guild.py` | guilde locale (API `/api/guild` : `GET`, `PATCH` nom et membres ; `/api/open` avec `guild: true` ajoute la vitrine ouverte) |
| `simulator.py` | simulateurs de dégâts et de combat (API `/api/sim/*`, voir `docs/SIMULATORS.md`) |
| `anim.html` | modèle animé du héros dans la fiche : rendu en direct depuis les fichiers publics d'E7 Codex (lecteur Spine du site), dans un cadre isolé (`sandbox`, CSP limitée à e7codex.com) sans accès à l'application ; la pose de la capture reste affichée hors ligne |
| `profiles.py` | profils dans `<données>/profiles/<id>/` (`profile.json` = Roster, `images/*.webp`) |
| `importer.py` | reconnaissance des captures (moteur `scanner/` calibré : 100 % sur captures PC réelles) |
| `viewer.py` | page vitrine = vitrine web existante (`render/webapp.py`) + poses issues des captures |
| `vitrine_file.py` | format `.e7v` (export / ouverture sécurisée) |

## Format `.e7v` (version 1)
Archive ZIP : `manifest.json` (`format = "e7showcase-vitrine"`, `version`, `player`,
`exported_at`, `app_version`), `profile.json` (Roster, `SCHEMA_VERSION`), `images/<clé>.webp`.
À l'ouverture tout est **non fiable** : noms en liste blanche (aucune extraction de chemin),
tailles plafonnées (200 Mo, 20 Mo par élément), roster validé par Pydantic, images décodées puis
ré-encodées. Une version plus récente que l'application est refusée avec un message clair.
Toute évolution incompatible → incrémenter `VERSION` et garder la lecture des anciennes.

## Contenu partagé
Les poses viennent des **captures du joueur** et ne voyagent que dans ses propres fichiers `.e7v` :
rien de tout cela n'entre dans le dépôt. Aucune donnée n'est envoyée sur Internet par l'application, sauf le plan de défense GvG que le
joueur choisit de publier sur Discord (webhook qu'il a lui-même enregistré).

## Construire l'installateur Windows
Automatique : workflow GitHub `Application Windows` (artefact `E7Showcase-Windows`, Release sur
tag `v*`). À la main, sous Windows :
```bat
pip install -e ".[app]" pyinstaller
pyinstaller packaging\e7showcase-app.spec --noconfirm
iscc packaging\windows\installer.iss
```
L'installateur (Inno Setup) crée le raccourci et associe les fichiers `.e7v`, sans droits
administrateur. Tout se fait dans la fenêtre de l'application : sans WebView2, un message
explique comment l'installer.

## Tests
`tests/test_app.py` : profils, aller-retour `.e7v`, fichiers hostiles, API (jeton, Host,
lecture seule des vitrines reçues). Bout en bout vérifié avec Playwright sur l'exécutable
PyInstaller : 6 captures réelles → 3 héros, 4 sets appris → export → ouverture ailleurs.

## Esthétique et animations
Thème, transitions entre onglets, apparitions, particules et micro-interactions : voir
`docs/UI_MOTION.md` (désactivables par le bouton « ✨ Effets visuels » et `prefers-reduced-motion`).
