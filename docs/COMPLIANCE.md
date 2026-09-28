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

**E7 Codex** (e7codex.com, archive fan-made qui reconnaît la propriété de Smilegate /
Super Creative ; robots.txt `Allow: /`) : le dépôt ne contient que des données factuelles
(codes, noms, élément, classe, rareté, chemins relatifs) générées par
`scripts/update_reference.py`. `e7showcase assets sync` ne télécharge que les héros du roster
du joueur (sauf `--all` explicite), une seule fois (cache local), avec une pause entre requêtes
et un User-Agent identifiable. Contact du site pour toute demande : contact@e7codex.com.

**Modèles animés** (`render --animated`) : le projet n'embarque pas le moteur d'animation Spine
(soumis à sa propre licence). Il ouvre la visionneuse publique d'E7 Codex dans un navigateur sans
interface et utilise son bouton d'export « WebP animé transparent », comme un joueur le ferait.
Un export par héros, mis en cache dans le dossier local ; jamais d'export en masse.

## Données personnelles
- Le roster reste **local** ; rien n'est envoyé sans commande explicite (`share`, `export`).
- Les captures peuvent contenir le pseudo et l'UID : elles restent dans le dossier de données
  local et ne doivent jamais être committées (`.gitignore`).
- Le webhook Discord est un secret : uniquement dans `.env` / variables d'environnement.
- Le bot stocke un roster par membre Discord ; `/roster-upload` écrase l'ancien, et un membre
  doit pouvoir supprimer ses données (commande `/roster-delete` prévue).

Projet communautaire non affilié à Smilegate.
