# Agents et skills Claude Code

Le projet embarque une équipe d'agents spécialisés (`.claude/agents/`) et des skills
(`.claude/skills/`) chargées à la demande. Claude Code les détecte automatiquement.

## Agents

| Agent | Modèle | Outils | Rôle |
|---|---|---|---|
| `e7-architect` | opus | lecture + web | Découpe une fonctionnalité multi-modules, assigne agents et skills, garde les contrats |
| `vision-ocr-engineer` | opus | lecture/écriture/bash | Capture, ROI, OCR, template matching, fixtures de captures |
| `e7-game-data-specialist` | sonnet | lecture/écriture/bash/web | Règles du jeu, référentiels, modèles, parseurs, import Fribbels |
| `showcase-designer` | sonnet | lecture/écriture/bash | Templates, CSS, rendu PNG, lisibilité Discord |
| `discord-integrator` | sonnet | lecture/écriture/bash/web | Webhook, bot slash-commands, données des membres |
| `qa-engineer` | sonnet | lecture/écriture/bash | Tests, non-régression OCR, définition de « terminé » |
| `compliance-reviewer` | sonnet | lecture seule (+bash) | CGU, secrets, vie privée, PI — verdict APPROUVÉ/BLOQUÉ |

## Skills

| Skill | Quand | Utilisée par |
|---|---|---|
| `e7-domain` | toute logique métier (stats, sets, gear score, Fribbels) | game-data, architect, qa |
| `calibrate-ocr-regions` | zone OCR fausse, mise à jour UI, nouveau ratio | vision |
| `e7-reference-data` | nouveau héros / set / langue | game-data |
| `render-showcase` | modification du rendu, production d'une vitrine | designer |
| `discord-integration` | webhook, bot, partage guilde | discord |
| `dev-checks` | fin de chaque tâche, avant commit | tous |

## Flux type d'une fonctionnalité

```
utilisateur ─► e7-architect (plan) ─► agent(s) spécialiste(s) + skill(s)
                                         │
                                         ▼
                                   qa-engineer (tests, dev-checks)
                                         │
                                         ▼
                               compliance-reviewer (si capture / partage / secrets)
                                         │
                                         ▼
                                      commit
```

Exemples de demandes :
- « Ajoute la lecture des étoiles et de l'éveil » → architect → vision-ocr-engineer
  (`calibrate-ocr-regions`) + game-data (modèle) → qa → compliance.
- « Fais une vue équipe GvG de 3 héros » → showcase-designer (`render-showcase`) → qa.
- « Commande /qui-a Ras vitesse>=200 » → discord-integrator (`discord-integration`) → qa → compliance.
