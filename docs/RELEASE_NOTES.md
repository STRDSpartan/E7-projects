# E7 Showcase 0.44.0

Grosse mise à jour de l'application de bureau : nouveaux onglets, guerre de guilde, exports,
nouvel habillage et application nettement plus rapide.

## Nouveautés
- **Onglets** : Vitrine, Simulateur de combat, Guilde, Armurerie, GvG.
- **Armurerie** : toutes vos pièces, portées (lues sur les captures « Infos de héros ») et
  non équipées (captures de l'infobulle d'un objet, avec son image) ; filtres par emplacement,
  set, stat principale et état.
- **Guilde** : membres (votre profil et les vitrines `.e7v` reçues), puissance, héros phares.
- **GvG** :
  - défenses de chaque membre (2 équipes de 3 et une tour), suivi des guerres (attaques,
    résultats, attaques restantes) et contres connus ;
  - test d'une équipe dans le simulateur, héros adverses estimés selon leur classe ;
  - plan de défense à copier pour Discord, en `.md` ou en `.csv` ;
  - publication sur Discord par webhook (plan, guerres, contres), mise à jour automatique des
    messages déjà publiés.
- **Exports et import tableur (.csv)** : défenses, contres, guerres, membres, profil complet
  (héros et armurerie), toute la guilde en un fichier, et import de ce fichier sur un autre PC.
- **Simulateur** : nombreuses mécaniques de héros ajoutées (dégâts additionnels, formules
  dynamiques, Mei Lin, Silvertide Christy…) et **rejeu animé** du combat type.

## Habillage
Nouveau thème, transitions entre onglets, particules, portraits de héros aux couleurs de leur
élément, tableaux GvG illustrés, notifications. Bouton « ✨ Effets visuels » pour tout couper
(coupé aussi automatiquement si Windows demande de réduire les animations).

## Rapidité et fiabilité
- Onglets Guilde et GvG jusqu'à 40 fois plus rapides, portraits instantanés.
- Vitrine 100 fois plus légère (images mises en cache, vignettes).
- Simulateur réparti sur plusieurs cœurs (environ 3 fois plus rapide sur 4 cœurs).
- Import des captures envoyé en binaire, plus léger en mémoire.
- Correction : deux modifications rapprochées (onglet Défenses) pouvaient s'écraser.
- Fichiers de guilde, GvG et Discord écrits de façon sûre (pas de fichier abîmé en cas de
  coupure) ; pages protégées contre tout contenu extérieur.

## À savoir
- Les pourcentages du simulateur ont légèrement changé une fois (nouveau découpage des
  combats) ; ils restent ensuite identiques d'une simulation et d'un PC à l'autre.
- Vos profils, vitrines et réglages sont conservés.
