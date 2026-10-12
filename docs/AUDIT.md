# Audit sécurité et performances — v0.42.0 (12/10/2026)

Mesures : guilde de 30 membres × 40 héros entièrement équipés, 5 guerres de 30 attaques
(script de bench local, meilleur de 3 appels, serveur de l'application).

| Requête | Avant | Après |
|---|---:|---:|
| Liste des profils | 73 ms | 3 ms |
| Page Guilde | 199 ms | 7 ms |
| Onglet GvG | 387 ms | 9 ms |
| Plan de défense | 320 ms | 9 ms |
| Modifier une défense | 283 ms | 13 ms |
| Portraits (60 héros) | 1 013 ms | 6 ms |
| Export CSV de toute la guilde | 833 ms | 187 ms |

## Performances
- **Cache des rosters** (`ProfileStore.peek`) : un roster n'est relu et revalidé que si son
  fichier a changé (date et taille) ; `load()` rend une copie modifiable. Les pages en lecture
  (guilde, GvG, armurerie, vitrine, CSV, simulateur, portraits) utilisent `peek()`.
- **Portraits** : index nom → héros construit une fois par état des profils (`generation`),
  résultats (même sans image) gardés jusqu'au prochain changement ou 2 min.
- **Simulateur** : passifs indexés par évènement, vitesse effective calculée une fois par
  action (résultats identiques, combat reproductible).
- **Simulateur sur plusieurs cœurs** (v0.43.0) : les combats sont répartis en 8 lots aux
  graines fixes, calculés par des processus partagés (`calc.battle`, démarrés en tâche de fond
  au lancement, arrêtés à la fermeture). 4 contre 4, 500 combats, 4 cœurs : 2,9 s → 0,8 s.
  Le résultat ne dépend pas du nombre de cœurs (identique avec ou sans parallélisme) ; sans
  processus disponibles, calcul sur place. Sous 120 combats, tout reste dans le même processus.
- **Import de captures** : envoi binaire, une requête par capture et 3 en parallèle
  (`POST /api/profiles/<id>/uploads`), au lieu d'un seul JSON en base64 (+33 % de taille, deux
  copies en mémoire). L'ancien format reste accepté.
- **Interface** : page gardée en mémoire par le serveur ; plus de flou d'arrière-plan sur
  chaque carte (coûteux pour la carte graphique) ; particules à ~30 images/s quand seules les
  poussières bougent, en pause quand la fenêtre n'a pas le focus ; décorations des nouveaux
  contenus regroupées une fois par image.

## Sécurité et fiabilité
- **Écritures concurrentes (bug corrigé)** : le serveur traite les requêtes en parallèle et les
  fichiers guilde/GvG/profils étaient lus, modifiés puis réécrits sans verrou ; deux
  modifications rapprochées (l'onglet Défenses enregistre à chaque choix) pouvaient s'écraser.
  Les modifications passent maintenant une par une (`AppState.write_lock`, verrou des profils,
  verrou des réglages Discord partagé avec les publications différées). Test :
  `test_concurrent_edits_are_not_lost`.
- **Écriture atomique** (`app/jsonfile.py`) : guilde, GvG et Discord sont écrits dans un fichier
  temporaire puis substitués ; le fichier du webhook est restreint (0600) avant d'être en place.
- **En-têtes** : l'interface et la vitrine envoient une CSP stricte (aucune ressource externe,
  pas d'affichage dans le cadre d'un autre site), `Referrer-Policy: no-referrer`.

## Points vérifiés sans anomalie
Serveur lié à 127.0.0.1, contrôle de l'en-tête Host (rebinding DNS), jeton de session sur
toute l'API ; aucun `innerHTML` alimenté par des données (seul l'emblème statique) ; JSON
intégré à la vitrine neutralisé (`safe_json`) ; identifiants de profil et de pièce filtrés
(pas de traversée de chemin) ; `.e7v` : taille, nombre d'entrées et taille par entrée bornés,
images ré-encodées ; CSV : formules neutralisées à l'export, taille bornée à l'import ;
webhook validé par expression régulière, jamais renvoyé en clair, mentions désactivées ;
aucun `eval`, `pickle`, `shell=True` ni désactivation TLS.

## Restant
- La vitrine (`/profile/<id>`) réintègre ses images à chaque ouverture (~50 ms).
- `ui.html` est gardé en mémoire : relancer l'application après l'avoir modifié.
