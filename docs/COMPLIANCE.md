# Conformité et vie privée

Epic Seven est édité par Smilegate. Les CGU interdisent en général les programmes tiers qui
**modifient le jeu, lisent sa mémoire, interceptent son trafic ou automatisent le gameplay**.
Ce projet est conçu pour rester du côté « outil de capture d'écran » :

| Pratique | Statut |
|---|---|
| Capture des pixels affichés à l'écran | ✅ utilisé (équivalent d'une capture manuelle) |
| OCR sur ces captures, en local | ✅ utilisé |
| Import d'un export Fribbels fourni par le joueur | ✅ utilisé |
| Lecture de la mémoire du processus | ❌ interdit dans ce dépôt |
| Interception / déchiffrement du trafic réseau | ❌ interdit dans ce dépôt |
| Modification de fichiers du client | ❌ interdit dans ce dépôt |
| Clics automatisés (mode `assisted`) | ⚠ **désactivé par défaut**, navigation de menus uniquement, jamais en combat. À l'utilisateur de vérifier les CGU en vigueur ; le mode `manual` est recommandé. |

Toute contribution introduisant une technique de la colonne ❌ doit être refusée
(l'agent `compliance-reviewer` le vérifie).

## Visuels du jeu (portraits, artefacts)
Propriété de Smilegate : jamais committés ni redistribués par le projet. Chaque joueur les place
dans son dossier de données local (`e7showcase assets`) ; toute synchronisation depuis un site
tiers doit respecter ses conditions d'utilisation et son robots.txt, et télécharger en local.

## Données personnelles
- Le roster reste **local** ; rien n'est envoyé sans commande explicite (`share`, `export`).
- Les captures peuvent contenir le pseudo et l'UID : elles restent dans le dossier de données
  local et ne doivent jamais être committées (`.gitignore`).
- Le webhook Discord est un secret : uniquement dans `.env` / variables d'environnement.
- Le bot stocke un roster par membre Discord ; `/roster-upload` écrase l'ancien, et un membre
  doit pouvoir supprimer ses données (commande `/roster-delete` prévue).

Projet communautaire non affilié à Smilegate.
