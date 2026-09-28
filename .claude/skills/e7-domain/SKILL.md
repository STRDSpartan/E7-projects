---
name: e7-domain
description: Règles et données du jeu Epic Seven utiles au projet - statistiques, emplacements d'équipement et stats principales autorisées, sets (2/4 pièces), amélioration +15, réforge, gear score communautaire, format d'export Fribbels. Charger avant de modifier models, calc, parsers, importers ou data/reference.
---

# Epic Seven — connaissances métier

## Statistiques (`models/stats.py::StatType`)
ATK, PV (HP), DEF — en valeur fixe **ou** en % ; Vitesse (fixe) ; Chances critiques %,
Dégâts critiques %, Efficacité %, Résistance aux effets %, Attaque double % (fiche héros
uniquement, jamais en substat d'équipement).

Sur la **fiche héros**, ATK/PV/DEF sont toujours des totaux absolus (d'où la conversion dans
`parsers/hero_parser.py`). Sur une **pièce**, « Attaque 8% » ≠ « Attaque 45 ».

## Emplacements et stat principale
| Emplacement | Stat principale |
|---|---|
| Arme | ATK fixe (imposée) |
| Casque | PV fixe (imposée) |
| Armure | DEF fixe (imposée) |
| Collier | ATK/PV/DEF (fixe ou %), CC %, DC % |
| Anneau | ATK/PV/DEF (fixe ou %), Efficacité %, Résistance % |
| Bottes | ATK/PV/DEF (fixe ou %), Vitesse |

`models/gear.py::FIXED_MAIN_STAT` encode les trois premières ; `parse_gear` rejette une
incohérence (signe d'une ROI mal calibrée).

## Substats
- 4 substats max ; une stat ne peut être à la fois principale et secondaire.
- Amélioration +0 → +15 : une amélioration de substat à +3, +6, +9, +12, +15 (5 au total).
- Rangs : Normal, Bon, Rare, Héroïque, Épique. Niveaux d'objet courants : 85, 88, 90 (réforge).
- `StatLine.rolls` = nombre d'améliorations tombées sur la stat (fourni par Fribbels).

## Sets
Bonus actif par tranche de 2 ou 4 pièces identiques ; 6 pièces = au plus un set 4 + un set 2,
ou trois sets 2. Référence : `data/reference/sets.json` — 24 sets du client FR (catalogue vérifié
en jeu) : Attaque, Défense, Santé, Vitesse, Critique, Destruction, Coup (≈ Hit), Résistance,
Vol de vie, Contre, Unité, Immunité, Rage, Infiltration (≈ Penetration), Vengeance, Blessure,
Protection, Tumulte (≈ Torrent), Riposte, Réaction, Engagement, Poursuite, Affaiblissement,
Implication. Champs `pieces_verified` et `en_mapping` (certain | probable | inconnu) : ne jamais
présenter comme certaine une correspondance « probable » ou « inconnue ».

## Gear score (`calc/gear_score.py`)
Convention Fribbels, sur les **substats** uniquement :
```
ATK% + DEF% + PV% + EFF + RES + VIT×2 + CC×1.6 + DC×1.14
+ ATK×3.46/39 + DEF×4.99/31 + PV×3.09/174
```
Exemple de test : VIT 10, CC 10, DC 14, ATK% 8 → 20 + 16 + 16 + 8 = **60.0**.

## Export Fribbels E7 Optimizer
```json
{"heroes": [{"id": "...", "name": "Ras", "stars": 6, "level": 60,
             "equippedStats": {"atk":..,"hp":..,"def":..,"spd":..,"cr":..,"cd":..,"eff":..,"res":..,"dac":..}}],
 "items":  [{"gear": "Weapon|Helmet|Armor|Necklace|Ring|Boots", "set": "SpeedSet", "rank": "Epic",
             "level": 85, "enhance": 15, "main": {"type": "Attack", "value": 515},
             "substats": [{"type": "CriticalHitChancePercent", "value": 5, "rolls": 1}],
             "equippedById": "<hero id>"}]}
```
Types de stats : `Attack, AttackPercent, Health, HealthPercent, Defense, DefensePercent, Speed,
CriticalHitChancePercent, CriticalHitDamagePercent, EffectivenessPercent, EffectResistancePercent`.
Le format varie selon les versions : l'importeur doit rester tolérant (clés absentes = défaut).

## Vocabulaire guilde
GvG (guerre de guilde, défenses par tour), RTA (arène temps réel), Wyvern/Banshee/Azimanak/Caides
(boss de chasse), Expédition, Chambre (Hall of Trials). Tags libres via `e7showcase tag`.
