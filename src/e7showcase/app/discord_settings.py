"""Réglages Discord de l'application : adresse du webhook du salon GvG.

    <dossier de données>/discord.json

L'adresse d'un webhook donne le droit d'écrire dans le salon : elle reste sur l'ordinateur
du joueur (jamais dans un fichier .e7v ni renvoyée en clair à l'interface).
"""

from __future__ import annotations

import contextlib
import json
from pathlib import Path

from e7showcase.publish.webhook import mask_webhook, valid_webhook


class DiscordSettings:
    def __init__(self, path: Path):
        self.path = path

    def webhook(self) -> str:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return ""
        url = data.get("gvg_webhook", "") if isinstance(data, dict) else ""
        return url if isinstance(url, str) and valid_webhook(url) else ""

    def set_webhook(self, url: str) -> None:
        url = url.strip()
        if url and not valid_webhook(url):
            raise ValueError(
                "adresse invalide : copiez l'URL du webhook depuis Discord "
                "(Paramètres du salon → Intégrations → Webhooks)"
            )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"gvg_webhook": url}), encoding="utf-8")
        with contextlib.suppress(OSError):  # lisible par le seul utilisateur (hors Windows)
            self.path.chmod(0o600)

    def status(self) -> dict[str, object]:
        url = self.webhook()
        return {"configured": bool(url), "hint": mask_webhook(url)}
