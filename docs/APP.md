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
3. La vitrine se construit : recherche, filtres (élément, classe, set), tris, fiche détaillée.
4. *Exporter la vitrine* → `vitrine-<joueur>.e7v`.
5. Le destinataire : double-clic sur le fichier (association installée) ou *Ouvrir une vitrine* →
   rangée dans « Vitrines reçues », consultation seule.

## Architecture (`src/e7showcase/app/`)
| Fichier | Rôle |
|---|---|
| `launcher.py` | point d'entrée `e7showcase-app [fichier.e7v]` : serveur local + fenêtre native (pywebview) ou navigateur (`--browser`) |
| `server.py` | serveur HTTP local (127.0.0.1, port aléatoire), API JSON, jeton de session + contrôle de l'en-tête Host |
| `ui.html` | interface (HTML/JS sans dépendance) |
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
rien de tout cela n'entre dans le dépôt. Aucune donnée n'est envoyée sur Internet par l'application.

## Construire l'installateur Windows
Automatique : workflow GitHub `Application Windows` (artefact `E7Showcase-Windows`, Release sur
tag `v*`). À la main, sous Windows :
```bat
pip install -e ".[app]" pyinstaller
pyinstaller packaging\e7showcase-app.spec --noconfirm
iscc packaging\windows\installer.iss
```
L'installateur (Inno Setup) crée le raccourci et associe les fichiers `.e7v`, sans droits
administrateur. Sans pywebview, `E7Showcase.exe --browser` ouvre l'interface dans le navigateur.

## Tests
`tests/test_app.py` : profils, aller-retour `.e7v`, fichiers hostiles, API (jeton, Host,
lecture seule des vitrines reçues). Bout en bout vérifié avec Playwright sur l'exécutable
PyInstaller : 6 captures réelles → 3 héros, 4 sets appris → export → ouverture ailleurs.
