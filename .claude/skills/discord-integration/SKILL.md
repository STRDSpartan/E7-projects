---
name: discord-integration
description: Configurer et faire évoluer la publication Discord (webhook de salon, bot discord.py avec slash commands /vitrine, /draft, /roster-upload), tester sans réseau et respecter limites et secrets. À utiliser pour src/e7showcase/publish ou quand l'utilisateur veut partager sa vitrine avec sa guilde.
---

# Intégration Discord

## Webhook (cas principal, aucun hébergement)
1. Discord : Paramètres du salon → Intégrations → Webhooks → Nouveau → Copier l'URL.
2. `.env` : `E7_DISCORD_WEBHOOK_URL=...` (jamais committé).
3. `e7showcase share "Ras" --message "Mon Ras GvG"`.

Implémentation : `publish/webhook.py::post_images` (multipart `payload_json` + `files[n]`,
10 fichiers max par message, découpage automatique).

Test sans réseau :
```python
import httpx


def handler(request):
    assert b"payload_json" in request.content
    return httpx.Response(204)


monkeypatch.setattr(
    httpx,
    "post",
    lambda *a, **kw: httpx.Client(transport=httpx.MockTransport(handler)).post(*a, **kw),
)
```

## Bot de guilde (extra `[bot]`)
1. Portail développeur Discord → Application → Bot → token dans `E7_DISCORD_BOT_TOKEN`.
2. Invitation avec les scopes `bot` + `applications.commands`, permissions *Send Messages*,
   *Attach Files*.
3. `e7showcase bot`. Commandes : `/roster-upload fichier`, `/vitrine [membre] [heros]`,
   `/draft heros`.

Règles :
- `interaction.response.defer()` avant tout rendu (> 3 s).
- Réponses éphémères pour les opérations sur les données personnelles.
- Valider les JSON uploadés avec `Roster.model_validate_json` et limiter leur taille.
- Extraire la logique (recherche de héros dans la guilde, filtres) en fonctions pures testées ;
  le fichier `bot.py` ne doit contenir que le câblage discord.py.

## Checklist avant merge
- Aucun secret dans le diff (voir agent `compliance-reviewer`).
- Skill `dev-checks` verte.
