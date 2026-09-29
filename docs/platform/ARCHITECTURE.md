# E7 Social — plateforme communautaire Epic Seven

Site où les joueurs s'inscrivent, tiennent un **profil complet**, publient leurs **vitrines,
clips et succès**, ajoutent des **amis** en cherchant leur pseudo et s'organisent en **guilde**
(discussion en temps réel + forum). Le scanner `e7showcase` reste l'outil qui produit le
`roster.json` publié comme vitrine.

## Vue d'ensemble

```
navigateur ── React (Vite, TypeScript) ──►  /api/*  (REST JSON, cookie de session)
                                        ──►  /api/ws/channels/{id}  (WebSocket chat)
                                        ──►  /media/*  (fichiers envoyés par les joueurs)
FastAPI ── SQLAlchemy 2 ── SQLite (dev) / PostgreSQL (prod), migrations Alembic
       └─ ChannelHub (diffusion chat en mémoire → Redis pub/sub en multi-instance)
```

| Dossier | Rôle |
|---|---|
| `platform/backend/app/models/` | 14 tables : utilisateurs, sessions, amitiés, publications, likes, commentaires, guildes, membres, candidatures, canaux, messages, sujets, messages de forum, notifications |
| `app/schemas/` | contrats d'entrée/sortie Pydantic (l'API ne renvoie jamais un modèle ORM brut) |
| `app/services.py` | règles partagées : relation entre joueurs, rang de guilde, visibilité des publications |
| `app/routers/` | `auth`, `users`, `friends`, `posts`, `media`, `notifications`, `guilds`, `chat`, `forum` |
| `app/realtime.py` | abonnés WebSocket par canal |
| `alembic/versions/` | migrations (`0001` = schéma initial) |
| `platform/frontend/src/pages/` | Connexion/inscription, Fil, Découvrir, Profil `/u/:pseudo`, Amis, Publier, Notifications, Réglages, Guildes, Guilde `/g/:tag` (Discussion · Forum · Membres · Candidatures), Sujet `/threads/:id` |

## Règles métier

- **Amis** : demande → acceptation ; une demande réciproque est acceptée d'office.
- **Visibilité** d'une publication : `public`, `friends` (amis acceptés) ou `guild` (membres de
  la guilde de l'auteur au moment de la publication). Une publication invisible répond 404.
- **Types** : `text` ; `vitrine` (roster e7showcase, 2 Mo max.) ; `clip` (vidéo envoyée via
  `/api/media`) ; `achievement` (capture + libellé). Les médias doivent venir de `/media/`.
- **Guilde** : une seule par joueur. Rôles `leader` > `officer` > `member`. Guilde ouverte =
  entrée directe, sinon candidature validée par un officier. Le chef transmet la direction
  avant de partir ; le dernier membre qui part dissout la guilde. On n'exclut qu'un rang inférieur.
- **Chat** : canaux `général`, `gvg`, `builds` créés d'office ; canaux « officiers » invisibles
  des membres. Historique paginé (`?before=id`), diffusion WebSocket (fermeture 4403 si non membre).
- **Forum** : sujets épinglés en tête, catégorie `annonces` réservée aux officiers, sujets
  verrouillables par les officiers.

## Sécurité

- Mots de passe **Argon2** ; politique : 10 caractères min., lettre + chiffre.
- Session serveur : jeton aléatoire dans un cookie `HttpOnly`, `SameSite=Lax` (`Secure` en
  production via `E7S_COOKIE_SECURE=true`) ; seule son empreinte SHA-256 est stockée.
- Envois de fichiers : liste blanche PNG/JPEG/WebP/GIF/MP4/WebM, **signature binaire vérifiée**,
  tailles plafonnées, noms aléatoires ; SVG/HTML refusés (pas de XSS stocké).
- Autorisations vérifiées côté serveur à chaque requête (le frontend ne fait que masquer).
- À faire avant ouverture publique : limitation de débit (connexion, inscription, messages),
  vérification d'e-mail, protection CSRF par en-tête dédié si le site sort du même domaine,
  CSP stricte, antivirus/transcodage des médias, sauvegardes chiffrées.

## RGPD et modération

- `GET /api/users/me/export` : export JSON complet (profil, publications, commentaires,
  messages, amis). `DELETE /api/users/me` (mot de passe requis) : suppression du compte ;
  les messages de chat/forum sont anonymisés pour ne pas casser les fils de discussion.
- Pas de collecte au-delà de l'e-mail et du profil public. Pas de pistage tiers.
- Contenus : les joueurs publient **leurs propres** captures et clips ; aucune illustration du jeu
  n'est redistribuée par la plateforme (rappel dans le formulaire de publication).
- À prévoir : signalement de contenu, file de modération, sanctions (masquage, bannissement),
  mentions légales et CGU, âge minimum.

## Démarrer

```bash
# API (SQLite, tables créées automatiquement en dev)
pip install -e "platform/backend[dev]"
cd platform/backend && uvicorn app.main:app --reload         # http://127.0.0.1:8000/docs
# Frontend (relaie /api et /media vers l'API)
cd platform/frontend && npm install && npm run dev            # http://localhost:5173
# Avec PostgreSQL
cd platform && docker compose up --build
```

Configuration par variables `E7S_*` (voir `app/config.py`) : `DATABASE_URL`, `CORS_ORIGINS`,
`COOKIE_SECURE`, `MEDIA_DIR`, `SESSION_DAYS`, `MAX_IMAGE_MB`, `MAX_VIDEO_MB`, `MAX_ROSTER_KB`.
Aucun secret n'est versionné.

## Vérifications

```bash
cd platform/backend && ruff format --check . && ruff check . && mypy && pytest
E7S_DATABASE_URL=sqlite:///$(mktemp -d)/m.db alembic upgrade head
cd platform/frontend && npm run build        # tsc strict + bundle
```
