---
name: platform-dev
description: Développer la plateforme web E7 Social (platform/backend FastAPI + platform/frontend React) - ajouter une route, une table, une page ; migrations Alembic ; vérifications backend/frontend et test de bout en bout. À utiliser pour tout changement sous platform/.
---

# Plateforme E7 Social

Référence : `docs/platform/ARCHITECTURE.md`.

## Ajouter une fonctionnalité
1. **Modèle** dans `app/models/` (typé `Mapped[...]`), exporté par `app/models/__init__.py`.
2. **Migration** : `E7S_DATABASE_URL=sqlite:///$(mktemp -d)/m.db alembic upgrade head` puis
   `alembic revision --autogenerate -m "..."` ; relire le fichier généré, puis `ruff format`.
3. **Schémas** Pydantic dans `app/schemas/` — ne jamais renvoyer un objet ORM.
4. **Route** dans `app/routers/` : autorisation serveur (`current_user`, `require_role`,
   `can_see_post`), messages d'erreur en français, 404 plutôt que 403 pour ce qui est invisible.
5. **Tests** `tests/` avec la fixture `make_user` (un client connecté par joueur).
6. **Frontend** : type dans `src/api.ts`, page dans `src/pages/`, route dans `src/main.tsx`.

## Vérifier
```bash
cd platform/backend && ruff format . && ruff check . && mypy && pytest
cd platform/frontend && npm run build
```
Bout en bout : lancer `uvicorn app.main:app` (avec `E7S_DATABASE_URL`/`E7S_MEDIA_DIR` vers un
dossier temporaire) et `npx vite preview`, puis Playwright avec
`executable_path=/opt/pw-browsers/chromium-*/chrome-linux/chrome` dans le conteneur web.

## Interdits
Secrets en clair, TLS désactivé, envoi de fichiers sans vérification de signature,
contournement des contrôles de rôle côté serveur, données réelles de joueurs dans les tests.
